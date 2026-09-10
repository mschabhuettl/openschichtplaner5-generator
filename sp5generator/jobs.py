"""Persistent local jobs. HTTP processes enqueue; a separate bounded worker solves."""

import contextlib
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


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS snapshots(id TEXT PRIMARY KEY,owner TEXT NOT NULL,revision INTEGER NOT NULL,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,owner TEXT NOT NULL,snapshot_id TEXT NOT NULL,payload TEXT NOT NULL,state TEXT NOT NULL,created_at REAL NOT NULL,started_at REAL,finished_at REAL,parameters TEXT NOT NULL,result TEXT,error TEXT);
            CREATE TABLE IF NOT EXISTS accepted(snapshot_id TEXT PRIMARY KEY,revision INTEGER NOT NULL,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS receipts(key TEXT PRIMARY KEY,owner TEXT NOT NULL,job_id TEXT NOT NULL,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,actor TEXT NOT NULL,job_id TEXT NOT NULL,created_at REAL NOT NULL,payload TEXT NOT NULL);
            """)
        os.chmod(self.path, 0o600)

    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

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
                "SELECT * FROM snapshots WHERE id=?", (snapshot.id,)
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
            conn.execute(
                "INSERT OR REPLACE INTO snapshots VALUES(?,?,?,?)",
                (snapshot.id, owner, revision, snapshot.model_dump_json()),
            )
        return snapshot

    def get_snapshot(self, id, owner):
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM snapshots WHERE id=? AND owner=?", (id, owner)
            ).fetchone()
        if not row:
            raise KeyError(id)
        return Snapshot.model_validate_json(row["payload"])

    def submit(self, id, owner, time_limit=30, partial=False):
        if not 0 < time_limit <= 600:
            raise ValueError(
                "Time limit must be greater than 0 and at most 600 seconds"
            )
        snapshot = self.get_snapshot(id, owner)
        job_id = str(uuid.uuid4())
        with self.transaction() as conn:
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
                    snapshot.model_dump_json(),
                    "queued",
                    time.time(),
                    json.dumps({"time_limit": time_limit, "partial": partial}),
                ),
            )
        return self.get_job(job_id, owner)

    def get_job(self, id, owner):
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE id=? AND owner=?", (id, owner)
            ).fetchone()
        if not row:
            raise KeyError(id)
        data = dict(row)
        data.pop("payload")
        data.pop("owner")
        data["parameters"] = json.loads(data["parameters"])
        data["result"] = json.loads(data["result"]) if data["result"] else None
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
            if result.snapshot_hash != snapshot_hash(snapshot):
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


def run_worker(path, once=False):
    store = Store(path)
    lock = open(str(path) + ".worker.lock", "a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise Conflict("A worker already owns this store") from None
    child = None
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
        while not stopping:
            with store.transaction() as conn:
                row = conn.execute(
                    "SELECT * FROM jobs WHERE state='queued' ORDER BY created_at LIMIT 1"
                ).fetchone()
                if row:
                    job = dict(row)
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
                target=_solve_child, args=(str(path), job, os.getpid())
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
                    child.terminate()
                    child.join(5)
                    if child.is_alive():
                        child.kill()
                    break
                child.join(0.2)
            child.join()
            with store.connect() as conn:
                conn.execute(
                    "UPDATE jobs SET state='failed',error='Worker stopped before result',finished_at=? WHERE id=? AND state='running'",
                    (time.time(), job["id"]),
                )
            child = None
            if once:
                break
    finally:
        if child and child.is_alive():
            child.terminate()
            child.join()
        signal.signal(signal.SIGINT, old_int)
        signal.signal(signal.SIGTERM, old_term)
        lock.close()
