"""Persistent local jobs. HTTP processes enqueue; a separate bounded worker solves."""

import contextlib
from datetime import datetime, timezone
import fcntl
import json
import multiprocessing
import os
from pathlib import Path
import signal
import sqlite3
import time
import uuid
from .models import Snapshot, Result


class Conflict(ValueError):
    pass


def _project_summary(payload):
    """Materialize list data once when writing, never when listing projects."""
    name = payload.get("metadata", {}).get("project_name", "")
    if not isinstance(name, str) or len(name) > 120:
        raise ValueError("Projektname muss ein Text mit höchstens 120 Zeichen sein")
    return {
        "project_name": name.strip(),
        "created_at": payload.get("created_at"),
        "period_start": payload.get("period_start"),
        "period_end": payload.get("period_end"),
        "source": payload.get("source", ""),
        "employee_count": len(payload.get("employees", [])),
        "shift_count": len(payload.get("shifts", [])),
        "demand_count": len(payload.get("demands", [])),
    }


class Store:
    def __init__(self, path):
        # A symlink or relative spelling must not create a second worker lock.
        self.path = str(Path(path).resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS snapshots(id TEXT PRIMARY KEY,owner TEXT NOT NULL,revision INTEGER NOT NULL,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,owner TEXT NOT NULL,snapshot_id TEXT NOT NULL,payload TEXT NOT NULL,state TEXT NOT NULL,created_at REAL NOT NULL,started_at REAL,finished_at REAL,parameters TEXT NOT NULL,result TEXT,error TEXT);
            CREATE TABLE IF NOT EXISTS accepted(snapshot_id TEXT PRIMARY KEY,revision INTEGER NOT NULL,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS receipts(key TEXT PRIMARY KEY,owner TEXT NOT NULL,job_id TEXT NOT NULL,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,actor TEXT NOT NULL,job_id TEXT NOT NULL,created_at REAL NOT NULL,payload TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS jobs_queue ON jobs(state,created_at);
            CREATE INDEX IF NOT EXISTS jobs_owner_created ON jobs(owner,created_at DESC);
            CREATE INDEX IF NOT EXISTS jobs_owner_snapshot_created ON jobs(owner,snapshot_id,created_at DESC);
            """)
        self._migrate_project_summaries()
        os.chmod(self.path, 0o600)

    def _migrate_project_summaries(self):
        """Upgrade 0.7 databases atomically without rewriting their snapshots.

        BEGIN IMMEDIATE also serializes simultaneous app/worker startup. A
        failed migration rolls back columns and backfill together for retry.
        """
        columns = {
            "project_name": "TEXT NOT NULL DEFAULT ''",
            "created_at": "TEXT",
            "updated_at": "REAL NOT NULL DEFAULT 0",
            "period_start": "TEXT",
            "period_end": "TEXT",
            "source": "TEXT NOT NULL DEFAULT ''",
            "employee_count": "INTEGER NOT NULL DEFAULT 0",
            "shift_count": "INTEGER NOT NULL DEFAULT 0",
            "demand_count": "INTEGER NOT NULL DEFAULT 0",
            "archived": "INTEGER NOT NULL DEFAULT 0",
            "summary_version": "INTEGER NOT NULL DEFAULT 0",
        }
        with self.transaction() as conn:
            existing = {row["name"] for row in conn.execute("PRAGMA table_info(snapshots)")}
            for name, definition in columns.items():
                if name not in existing:
                    conn.execute(f"ALTER TABLE snapshots ADD COLUMN {name} {definition}")
            for row in conn.execute("SELECT id,payload FROM snapshots WHERE summary_version=0"):
                payload = json.loads(row["payload"])
                # Previously unrestricted metadata must not prevent upgrading.
                metadata = dict(payload.get("metadata", {}))
                name = metadata.get("project_name", "")
                metadata["project_name"] = name[:120] if isinstance(name, str) else ""
                summary = _project_summary({**payload, "metadata": metadata})
                try:
                    created = datetime.fromisoformat(summary["created_at"])
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                    updated_at = created.timestamp()
                except (TypeError, ValueError, OverflowError, OSError):
                    updated_at = 0
                setters = ",".join(f"{key}=?" for key in summary)
                conn.execute(
                    f"UPDATE snapshots SET {setters},updated_at=?,summary_version=1 WHERE id=?",
                    (*summary.values(), updated_at, row["id"]),
                )
            # The project picker is answered entirely from this compact index;
            # SQLite need not touch any pages containing personnel JSON.
            conn.execute("""CREATE INDEX IF NOT EXISTS snapshots_owner_recent ON snapshots(
                owner,archived,updated_at DESC,id DESC,revision,project_name,created_at,
                period_start,period_end,source,employee_count,shift_count,demand_count)""")
            conn.execute("CREATE INDEX IF NOT EXISTS snapshots_summary_version ON snapshots(summary_version)")

    @contextlib.contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=10000")
            yield conn
        finally:
            # sqlite3.Connection.__exit__ commits/rolls back, but does not close.
            conn.close()

    @contextlib.contextmanager
    def transaction(self):
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def save_snapshot(self, snapshot, owner):
        with self.transaction() as conn:
            current = conn.execute(
                "SELECT owner,revision FROM snapshots WHERE id=?", (snapshot.id,)
            ).fetchone()
            if current:
                if current["owner"] != owner:
                    raise PermissionError("Snapshot belongs to another account")
                if snapshot.revision != str(current["revision"]):
                    raise Conflict("Snapshot revision changed")
                revision = current["revision"] + 1
            else:
                revision = 1
            snapshot = snapshot.model_copy(
                update={"revision": str(revision)}, deep=True
            )
            self._write_snapshot(conn, snapshot, owner)
        return snapshot

    @staticmethod
    def _write_snapshot(conn, snapshot, owner):
        summary = _project_summary(snapshot.model_dump(mode="json"))
        columns = ["id", "owner", "revision", "payload", *summary, "updated_at", "summary_version"]
        update = ",".join(f"{key}=excluded.{key}" for key in columns if key not in {"id", "owner"})
        conn.execute(
            f"INSERT INTO snapshots({','.join(columns)}) VALUES({','.join('?' for _ in columns)}) "
            f"ON CONFLICT(id) DO UPDATE SET {update}",
            (snapshot.id, owner, int(snapshot.revision), snapshot.model_dump_json(),
             *summary.values(), time.time(), 1),
        )

    def get_snapshot(self, id, owner):
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM snapshots WHERE id=? AND owner=?", (id, owner)
            ).fetchone()
        if not row:
            raise KeyError(id)
        return Snapshot.model_validate_json(row["payload"])

    def list_snapshots(self, owner, archived=False, limit=200, offset=0):
        """Summaries for reopening saved work, without personnel or source data."""
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("Project list limit must be between 1 and 1000")
        if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= 1_000_000:
            raise ValueError("Project list offset must be between 0 and 1000000")
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT id,revision,project_name,created_at,updated_at,period_start,
                period_end,source,employee_count,shift_count,demand_count,archived
                FROM snapshots WHERE owner=? AND archived=?
                ORDER BY updated_at DESC,id DESC LIMIT ? OFFSET ?""",
                (owner, bool(archived), limit, offset),
            ).fetchall()
        return [{**dict(row), "archived": bool(row["archived"])} for row in rows]

    def copy_snapshot(self, id, owner, revision, project_name=None):
        with self.transaction() as conn:
            row = self._project_for_update(conn, id, owner, revision)
            snapshot = Snapshot.model_validate_json(row["payload"])
            snapshot.id = str(uuid.uuid4())
            snapshot.revision = "1"
            snapshot.created_at = datetime.now(timezone.utc)
            original_name = snapshot.metadata.get("project_name")
            fallback = original_name if isinstance(original_name, str) and original_name.strip() else "Projekt"
            snapshot.metadata["project_name"] = project_name if project_name is not None else f"{fallback[:112]} – Kopie"
            # A copy does not share the original project's synthetic acceptance.
            snapshot.metadata.pop("accepted_revision", None)
            self._write_snapshot(conn, snapshot, owner)
        return snapshot

    def set_archived(self, id, owner, revision, archived):
        with self.transaction() as conn:
            row = self._project_for_update(conn, id, owner, revision)
            snapshot = Snapshot.model_validate_json(row["payload"])
            if bool(row["archived"]) != bool(archived):
                if archived and conn.execute(
                    "SELECT 1 FROM jobs WHERE snapshot_id=? AND owner=? AND state IN ('queued','running') LIMIT 1",
                    (id, owner),
                ).fetchone():
                    raise Conflict("Laufende Berechnung zuerst beenden oder abbrechen")
                snapshot.revision = str(row["revision"] + 1)
                self._write_snapshot(conn, snapshot, owner)
                conn.execute("UPDATE snapshots SET archived=? WHERE id=?", (bool(archived), id))
        return snapshot

    @staticmethod
    def _project_for_update(conn, id, owner, revision):
        row = conn.execute("SELECT * FROM snapshots WHERE id=? AND owner=?", (id, owner)).fetchone()
        if row is None:
            raise KeyError(id)
        if str(revision) != str(row["revision"]):
            raise Conflict("Snapshot revision changed; reload before changing this project")
        return row

    def submit(self, id, owner, time_limit=30, partial=False, revision=None):
        if not 0 < time_limit <= 600:
            raise ValueError(
                "Time limit must be greater than 0 and at most 600 seconds"
            )
        job_id = str(uuid.uuid4())
        with self.transaction() as conn:
            snapshot = conn.execute(
                "SELECT payload,revision,archived FROM snapshots WHERE id=? AND owner=?",
                (id, owner),
            ).fetchone()
            if not snapshot:
                raise KeyError(id)
            if snapshot["archived"]:
                raise Conflict("Archiviertes Projekt vor einer Berechnung wiederherstellen")
            if revision is not None and str(revision) != str(snapshot["revision"]):
                raise Conflict("Snapshot revision changed; reload before calculation")
            active = conn.execute(
                "SELECT count(*) FROM jobs WHERE state IN ('queued','running')"
            ).fetchone()[0]
            if active >= 20:
                raise Conflict("Queue capacity reached")
            conn.execute(
                "INSERT INTO jobs(id,owner,snapshot_id,payload,state,created_at,parameters) VALUES(?,?,?,?,?,?,?)",
                (
                    job_id,
                    owner,
                    id,
                    snapshot["payload"],
                    "queued",
                    time.time(),
                    json.dumps({"time_limit": time_limit, "partial": partial}),
                ),
            )
        return self.get_job(job_id, owner)

    def list_jobs(self, owner, snapshot_id=None, limit=50):
        """Return bounded job summaries; retrieve full results only on demand."""
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
            raise ValueError("Job list limit must be between 1 and 200")
        query = """SELECT id,snapshot_id,state,created_at,started_at,finished_at,
        parameters,error FROM jobs WHERE owner=?"""
        parameters = [owner]
        if snapshot_id is not None:
            query += " AND snapshot_id=?"
            parameters.append(snapshot_id)
        query += " ORDER BY created_at DESC,rowid DESC LIMIT ?"
        parameters.append(limit)
        with self.connect() as conn:
            rows = conn.execute(query, parameters).fetchall()
        return [
            {**dict(row), "parameters": json.loads(row["parameters"])}
            for row in rows
        ]

    def get_job_snapshot(self, id, owner):
        """Recover exactly the revision solved, even after later snapshot edits."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT payload FROM jobs WHERE id=? AND owner=?", (id, owner)
            ).fetchone()
        if not row:
            raise KeyError(id)
        return Snapshot.model_validate_json(row["payload"])

    def get_job(self, id, owner):
        with self.connect() as conn:
            row = conn.execute(
                """SELECT id,snapshot_id,state,created_at,started_at,finished_at,
                parameters,result,error FROM jobs WHERE id=? AND owner=?""", (id, owner)
            ).fetchone()
        if not row:
            raise KeyError(id)
        data = dict(row)
        data["parameters"] = json.loads(data["parameters"])
        data["result"] = json.loads(data["result"]) if data["result"] else None
        return data

    def get_job_status(self, id, owner):
        """Polling never reads a stored input or a possibly large result."""
        with self.connect() as conn:
            row = conn.execute(
                """SELECT rowid,id,snapshot_id,state,created_at,started_at,finished_at,
                parameters,error FROM jobs WHERE id=? AND owner=?""", (id, owner)
            ).fetchone()
            if not row:
                raise KeyError(id)
            queue_position = None
            if row["state"] == "queued":
                queue_position = conn.execute(
                    """SELECT count(*) FROM jobs WHERE state='queued'
                    AND (created_at<? OR (created_at=? AND rowid<=?))""",
                    (row["created_at"], row["created_at"], row["rowid"]),
                ).fetchone()[0]
        data = dict(row)
        data.pop("rowid")
        data["parameters"] = json.loads(data["parameters"])
        data["queue_position"] = queue_position
        end = data["finished_at"] if data["finished_at"] is not None else time.time()
        data["elapsed_seconds"] = max(0, end - data["started_at"]) if data["started_at"] is not None else 0
        return data

    def cancel(self, id, owner):
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT state FROM jobs WHERE id=? AND owner=?", (id, owner)
            ).fetchone()
            if not row:
                raise KeyError(id)
            if row["state"] in ("queued", "running"):
                conn.execute(
                    "UPDATE jobs SET state='cancelled',finished_at=? WHERE id=?",
                    (time.time(), id),
                )
        return self.get_job(id, owner)

    def apply_synthetic(self, job_id, owner, key):
        """Atomic acceptance for the isolated canonical synthetic test store only."""
        from .domain import snapshot_hash
        from .validator import validate

        if not key or len(key) > 128:
            raise ValueError("Idempotency key required (at most 128 characters)")
        with self.transaction() as conn:
            receipt = conn.execute(
                "SELECT * FROM receipts WHERE key=?", (key,)
            ).fetchone()
            if receipt:
                if receipt["owner"] != owner or receipt["job_id"] != job_id:
                    raise Conflict("Idempotency key is already in use")
                return json.loads(receipt["payload"])
            job = conn.execute(
                "SELECT * FROM jobs WHERE id=? AND owner=?", (job_id, owner)
            ).fetchone()
            if not job:
                raise KeyError(job_id)
            if job["state"] != "succeeded":
                raise Conflict("Only completed jobs can be accepted")
            snapshot = Snapshot.model_validate_json(job["payload"])
            if snapshot.source != "synthetic":
                raise Conflict(
                    "Native source acceptance is not supported by this store"
                )
            current = conn.execute(
                "SELECT * FROM snapshots WHERE id=?", (snapshot.id,)
            ).fetchone()
            if not current or snapshot_hash(
                Snapshot.model_validate_json(current["payload"])
            ) != snapshot_hash(snapshot):
                raise Conflict("Snapshot changed; recalculate before acceptance")
            result = Result.model_validate_json(job["result"])
            if result.snapshot_id != snapshot.id or result.snapshot_hash != snapshot_hash(snapshot):
                raise Conflict("Result belongs to a different snapshot")
            validation = validate(snapshot, result.assignments)
            if not validation.valid or not validation.complete:
                raise Conflict("A complete independently valid result is required")
            accepted = conn.execute(
                "SELECT revision FROM accepted WHERE snapshot_id=?", (snapshot.id,)
            ).fetchone()
            expected = int(snapshot.metadata.get("accepted_revision", 0))
            if (accepted["revision"] if accepted else 0) != expected:
                raise Conflict("Accepted schedule changed since the snapshot")
            revision = expected + 1
            conn.execute(
                "INSERT OR REPLACE INTO accepted VALUES(?,?,?)",
                (snapshot.id, revision, result.model_dump_json()),
            )
            output = {
                "status": "applied",
                "backend": "synthetic-test-store",
                "revision": revision,
                "job_id": job_id,
                "assignments": len(result.assignments),
            }
            payload = json.dumps(output)
            conn.execute(
                "INSERT INTO receipts VALUES(?,?,?,?)", (key, owner, job_id, payload)
            )
            conn.execute(
                "INSERT INTO audit(actor,job_id,created_at,payload) VALUES(?,?,?,?)",
                (owner, job_id, time.time(), payload),
            )
            return output


def _solve_child(path, job, parent_pid):
    # Linux prevents orphaned optimization after an abrupt worker exit.
    import sys

    if sys.platform == "linux":
        import ctypes

        libc = ctypes.CDLL(None)
        if libc.prctl(1, signal.SIGTERM, 0, 0, 0) != 0:
            raise RuntimeError("Cannot configure worker child lifecycle")
        if os.getppid() != parent_pid:
            return
    try:
        from .solver import solve

        result = solve(
            Snapshot.model_validate_json(job["payload"]),
            **json.loads(job["parameters"]),
        )
        store = Store(path)
        with store.connect() as conn:
            conn.execute(
                "UPDATE jobs SET state='succeeded',result=?,finished_at=? WHERE id=? AND state='running'",
                (result.model_dump_json(), time.time(), job["id"]),
            )
    except BaseException:
        with Store(path).connect() as conn:
            conn.execute(
                "UPDATE jobs SET state='failed',error='Calculation failed; input and environment need local review',finished_at=? WHERE id=? AND state='running'",
                (time.time(), job["id"]),
            )


def _terminate_child(child):
    """Bound shutdown even if a calculation ignores the graceful signal."""
    if child.is_alive():
        child.terminate()
        child.join(5)
        if child.is_alive():
            child.kill()
            child.join(5)
        if child.is_alive():
            raise RuntimeError("Calculation process could not be stopped")


def run_worker(path, once=False, ready=None):
    store = Store(path)
    lock = open(store.path + ".worker.lock", "a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        raise Conflict("A worker already owns this store") from None
    except BaseException:
        lock.close()
        raise
    child = None
    active_job = None
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    old_int, old_term = (
        signal.signal(signal.SIGINT, stop),
        signal.signal(signal.SIGTERM, stop),
    )
    try:
        with store.connect() as conn:
            conn.execute(
                "UPDATE jobs SET state='failed',error='Worker interrupted; explicit resubmission required',finished_at=? WHERE state='running'",
                (time.time(),),
            )
        if ready is not None:
            ready.set()
        while not stopping:
            with store.transaction() as conn:
                row = conn.execute(
                    "SELECT * FROM jobs WHERE state='queued' ORDER BY created_at LIMIT 1"
                ).fetchone()
                if row:
                    job = dict(row)
                    active_job = job["id"]
                    conn.execute(
                        "UPDATE jobs SET state='running',started_at=? WHERE id=?",
                        (time.time(), job["id"]),
                    )
            if not row:
                if once:
                    break
                time.sleep(0.25)
                continue
            child = multiprocessing.get_context("spawn").Process(
                target=_solve_child, args=(store.path, job, os.getpid())
            )
            child.start()
            deadline = (
                time.monotonic() + json.loads(job["parameters"])["time_limit"] + 120
            )
            while child.is_alive():
                with store.connect() as conn:
                    state = conn.execute(
                        "SELECT state FROM jobs WHERE id=?", (job["id"],)
                    ).fetchone()[0]
                if stopping or state == "cancelled" or time.monotonic() > deadline:
                    _terminate_child(child)
                    break
                child.join(0.2)
            child.join()
            with store.connect() as conn:
                conn.execute(
                    "UPDATE jobs SET state='failed',error=?,finished_at=? WHERE id=? AND state='running'",
                    (
                        f"Calculation process exited before result (exit code {child.exitcode})",
                        time.time(),
                        job["id"],
                    ),
                )
            child.close()
            child = None
            active_job = None
            if once:
                break
    finally:
        try:
            if child is not None:
                _terminate_child(child)
                child.close()
        finally:
            try:
                if active_job is not None:
                    with store.connect() as conn:
                        conn.execute(
                            "UPDATE jobs SET state='failed',error='Worker stopped before result',finished_at=? WHERE id=? AND state='running'",
                            (time.time(), active_job),
                        )
            finally:
                signal.signal(signal.SIGINT, old_int)
                signal.signal(signal.SIGTERM, old_term)
                lock.close()
