import sqlite3
import pytest
from sp5generator.demo import make_demo
from sp5generator.jobs import Conflict, Store


def test_store_revision_owner_and_cancel(tmp_path):
    store = Store(tmp_path / "jobs.sqlite")
    snapshot = store.save_snapshot(make_demo(), "test-owner")
    assert snapshot.revision == "1"
    with pytest.raises(KeyError):
        store.get_snapshot(snapshot.id, "different-owner")
    changed = store.save_snapshot(snapshot, "test-owner")
    assert changed.revision == "2"
    with pytest.raises(Conflict):
        store.save_snapshot(snapshot, "test-owner")
    job = store.submit(snapshot.id, "test-owner", 1)
    assert job["state"] == "queued"
    assert store.cancel(job["id"], "test-owner")["state"] == "cancelled"
    assert store.cancel(job["id"], "test-owner")["state"] == "cancelled"


def test_acceptance_is_atomic_and_stale_snapshot_rejected(tmp_path):
    from sp5generator.solver import solve

    store = Store(tmp_path / "jobs.sqlite")
    snapshot = store.save_snapshot(make_demo(days=1), "test-owner")
    job = store.submit(snapshot.id, "test-owner", 5)
    result = solve(snapshot, time_limit=5)
    assert result.validation.complete
    with store.connect() as conn:
        conn.execute(
            "UPDATE jobs SET state='succeeded',result=? WHERE id=?",
            (result.model_dump_json(), job["id"]),
        )
    # Audit failure must roll back both assignments and receipt.
    with store.connect() as conn:
        conn.execute(
            "CREATE TRIGGER fail_audit BEFORE INSERT ON audit BEGIN SELECT RAISE(ABORT,'injected failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError):
        store.apply_synthetic(job["id"], "test-owner", "retry-key")
    with store.connect() as conn:
        assert conn.execute("SELECT count(*) FROM accepted").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM receipts").fetchone()[0] == 0
        conn.execute("DROP TRIGGER fail_audit")
    receipt = store.apply_synthetic(job["id"], "test-owner", "retry-key")
    assert store.apply_synthetic(job["id"], "test-owner", "retry-key") == receipt
    with pytest.raises(Conflict):
        store.apply_synthetic(job["id"], "test-owner", "new-key")
    with store.connect() as conn:
        assert conn.execute("SELECT count(*) FROM audit").fetchone()[0] == 1
    store.save_snapshot(snapshot, "test-owner")
    with pytest.raises(Conflict):
        store.apply_synthetic(job["id"], "test-owner", "third-key")


@pytest.mark.parametrize("mismatch", ["id", "hash"])
def test_acceptance_rejects_mismatched_result_without_writes(tmp_path, mismatch):
    from sp5generator.solver import solve

    store = Store(tmp_path / "jobs.sqlite")
    snapshot = store.save_snapshot(make_demo(days=1), "test-owner")
    job = store.submit(snapshot.id, "test-owner", 5)
    result = solve(snapshot, time_limit=5)
    assert result.validation.valid and result.validation.complete
    original = result.model_dump_json()
    if mismatch == "id":
        result.snapshot_id = "different-synthetic-project"
    else:
        result.snapshot_hash = "stale-hash"
    with store.connect() as conn:
        conn.execute("UPDATE jobs SET state='succeeded',result=? WHERE id=?",
                     (result.model_dump_json(), job["id"]))
    with pytest.raises(Conflict, match="different snapshot"):
        store.apply_synthetic(job["id"], "test-owner", "retry-key")
    with store.connect() as conn:
        for table in ("accepted", "receipts", "audit"):
            assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
        conn.execute("UPDATE jobs SET result=? WHERE id=?", (original, job["id"]))
    # Failed acceptance must not consume the idempotency key.
    receipt = store.apply_synthetic(job["id"], "test-owner", "retry-key")
    assert receipt["status"] == "applied" and receipt["revision"] == 1


def test_worker_process_produces_persistent_result(tmp_path):
    import subprocess
    import sys

    store = Store(tmp_path / "jobs.sqlite")
    snapshot = store.save_snapshot(make_demo(days=1), "test-owner")
    job = store.submit(snapshot.id, "test-owner", 5)
    worker = subprocess.run(
        [
            sys.executable,
            "-m",
            "sp5generator.cli",
            "worker",
            "--store",
            store.path,
            "--once",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert worker.returncode == 0, worker.stderr
    loaded = Store(store.path).get_job(job["id"], "test-owner")
    assert loaded["state"] == "succeeded"
    assert loaded["result"]["validation"]["complete"]


def test_concurrent_acceptance_creates_one_receipt(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from sp5generator.solver import solve

    store = Store(tmp_path / "jobs.sqlite")
    snapshot = store.save_snapshot(make_demo(days=1), "test-owner")
    job = store.submit(snapshot.id, "test-owner", 5)
    result = solve(snapshot, time_limit=5)
    with store.connect() as conn:
        conn.execute(
            "UPDATE jobs SET state='succeeded',result=? WHERE id=?",
            (result.model_dump_json(), job["id"]),
        )
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(
            pool.map(
                lambda _: store.apply_synthetic(job["id"], "test-owner", "same-key"),
                range(2),
            )
        )
    assert receipts[0] == receipts[1]
    with store.connect() as conn:
        assert conn.execute("SELECT count(*) FROM audit").fetchone()[0] == 1


def test_running_job_cancel_and_restart_recovery(tmp_path):
    import subprocess
    import sys
    import time

    store = Store(tmp_path / "jobs.sqlite")
    snapshot = store.save_snapshot(make_demo(employees=120, days=31), "test-owner")
    job = store.submit(snapshot.id, "test-owner", 30)
    worker = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "sp5generator.cli",
            "worker",
            "--store",
            store.path,
            "--once",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 10
        while (
            store.get_job(job["id"], "test-owner")["state"] == "queued"
            and time.monotonic() < deadline
        ):
            time.sleep(0.02)
        assert store.get_job(job["id"], "test-owner")["state"] == "running"
        store.cancel(job["id"], "test-owner")
        worker.wait(timeout=10)
        assert store.get_job(job["id"], "test-owner")["state"] == "cancelled"
    finally:
        if worker.poll() is None:
            worker.terminate()
            worker.wait(timeout=10)
    # Simulate persisted interrupted state, without leaving an orphan process.
    with store.connect() as conn:
        conn.execute("UPDATE jobs SET state='running' WHERE id=?", (job["id"],))
    outcome = subprocess.run(
        [
            sys.executable,
            "-m",
            "sp5generator.cli",
            "worker",
            "--store",
            store.path,
            "--once",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert outcome.returncode == 0
    recovered = store.get_job(job["id"], "test-owner")
    assert recovered["state"] == "failed"
    assert "interrupted" in recovered["error"]


def test_recovery_lists_are_scoped_and_preserve_original_job_snapshot(tmp_path):
    store = Store(tmp_path / "jobs.sqlite")
    original = store.save_snapshot(make_demo(days=1), "test-owner")
    original_job = store.submit(original.id, "test-owner", revision=original.revision)
    changed = original.model_copy(deep=True)
    changed.employees[0].name = "Updated synthetic employee"
    changed = store.save_snapshot(changed, "test-owner")
    latest_job = store.submit(changed.id, "test-owner", partial=True)
    other = make_demo(days=2)
    other.id = "another-synthetic-snapshot"
    other = store.save_snapshot(other, "another-owner")
    other_job = store.submit(other.id, "another-owner")

    reopened = Store(store.path)
    snapshots = reopened.list_snapshots("test-owner")
    assert len(snapshots) == 1
    assert snapshots[0]["revision"] == 2
    assert snapshots[0]["period_start"] == original.period_start.isoformat()
    assert snapshots[0]["employee_count"] == len(original.employees)
    assert "employees" not in snapshots[0]
    jobs = reopened.list_jobs("test-owner")
    assert [job["id"] for job in jobs] == [latest_job["id"], original_job["id"]]
    assert jobs[0]["parameters"]["partial"] is True
    assert "result" not in jobs[0] and "payload" not in jobs[0]
    assert reopened.list_jobs("test-owner", snapshot_id=other.id) == []
    assert len(reopened.list_jobs("test-owner", limit=1)) == 1
    assert reopened.get_job_snapshot(original_job["id"], "test-owner") == original
    with pytest.raises(KeyError):
        reopened.get_job_snapshot(other_job["id"], "test-owner")


@pytest.mark.parametrize("limit", [0, 201, -1, True, 1.5, "10"])
def test_recovery_list_limit_is_bounded(tmp_path, limit):
    store = Store(tmp_path / "jobs.sqlite")
    with pytest.raises(ValueError):
        store.list_jobs("test-owner", limit=limit)


def test_submit_rejects_stale_revision_without_enqueuing(tmp_path):
    store = Store(tmp_path / "jobs.sqlite")
    original = store.save_snapshot(make_demo(days=1), "test-owner")
    changed = store.save_snapshot(original, "test-owner")
    with pytest.raises(Conflict, match="revision changed"):
        store.submit(original.id, "test-owner", revision=original.revision)
    assert store.list_jobs("test-owner") == []
    job = store.submit(changed.id, "test-owner", revision=changed.revision)
    assert store.get_job_snapshot(job["id"], "test-owner").revision == changed.revision


def test_connections_are_closed_after_read_and_failure(tmp_path):
    store = Store(tmp_path / "jobs.sqlite")
    with store.connect() as connection:
        assert connection.execute("SELECT 1").fetchone()[0] == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")
    with pytest.raises(RuntimeError):
        with store.transaction() as connection:
            raise RuntimeError("synthetic failure")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")


def test_worker_lock_uses_canonical_database_path(tmp_path):
    import fcntl
    from pathlib import Path
    from sp5generator.jobs import run_worker

    store = Store(tmp_path / "jobs.sqlite")
    alias = tmp_path / "alias.sqlite"
    alias.symlink_to(Path(store.path))
    with open(store.path + ".worker.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(Conflict, match="already owns"):
            run_worker(alias, once=True)


@pytest.mark.parametrize("failure_point", ["creation", "start"])
def test_worker_process_start_failure_finishes_job_and_releases_lock(
    tmp_path, monkeypatch, failure_point
):
    import multiprocessing
    from sp5generator.jobs import run_worker

    store = Store(tmp_path / "jobs.sqlite")
    snapshot = store.save_snapshot(make_demo(days=1), "test-owner")
    job = store.submit(snapshot.id, "test-owner")
    context = multiprocessing.get_context("spawn")
    original_process = context.Process

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic process start failure")

    def create(*args, **kwargs):
        process = original_process(*args, **kwargs)
        monkeypatch.setattr(process, "start", fail)
        return process

    with monkeypatch.context() as patch:
        patch.setattr(context, "Process", fail if failure_point == "creation" else create)
        with pytest.raises(RuntimeError, match="synthetic process start failure"):
            run_worker(store.path, once=True)
    recovered = store.get_job(job["id"], "test-owner")
    assert recovered["state"] == "failed"
    assert recovered["finished_at"] is not None
    run_worker(store.path, once=True)


def test_concurrent_submit_respects_global_queue_capacity(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    store = Store(tmp_path / "jobs.sqlite")
    snapshot = store.save_snapshot(make_demo(days=1), "test-owner")
    for _ in range(19):
        store.submit(snapshot.id, "test-owner")

    def submit(_):
        try:
            return store.submit(snapshot.id, "test-owner")["state"]
        except Conflict:
            return "full"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(submit, range(2))) == ["full", "queued"]
    assert len(store.list_jobs("test-owner")) == 20


def test_spawned_worker_announces_readiness_only_after_exclusive_recovery(tmp_path):
    import multiprocessing
    from sp5generator.jobs import run_worker

    store = Store(tmp_path / "jobs.sqlite")
    snapshot = store.save_snapshot(make_demo(days=1), "test-owner")
    job = store.submit(snapshot.id, "test-owner")
    with store.connect() as connection:
        connection.execute("UPDATE jobs SET state='running' WHERE id=?", (job["id"],))

    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    duplicate_ready = context.Event()
    worker = context.Process(target=run_worker, args=(store.path, False, ready))
    duplicate = context.Process(
        target=run_worker, args=(store.path, True, duplicate_ready)
    )
    worker.start()
    try:
        assert ready.wait(10), "Worker did not announce successful startup"
        assert worker.is_alive()
        assert store.get_job(job["id"], "test-owner")["state"] == "failed"
        duplicate.start()
        duplicate.join(10)
        assert duplicate.exitcode == 1
        assert not duplicate_ready.is_set()
        assert worker.is_alive()
    finally:
        for process in (duplicate, worker):
            if process.is_alive():
                process.terminate()
                process.join(10)
                if process.is_alive():
                    process.kill()
                    process.join(5)
            process.close()


def test_abrupt_calculation_exit_preserves_diagnostic_code(tmp_path, monkeypatch):
    import multiprocessing
    import os
    from sp5generator.jobs import run_worker

    store = Store(tmp_path / "jobs.sqlite")
    snapshot = store.save_snapshot(make_demo(days=1), "test-owner")
    job = store.submit(snapshot.id, "test-owner")
    context = multiprocessing.get_context("spawn")
    original_process = context.Process
    monkeypatch.setattr(
        context,
        "Process",
        lambda **kwargs: original_process(target=os._exit, args=(23,)),
    )
    run_worker(store.path, once=True)
    failed = store.get_job(job["id"], "test-owner")
    assert failed["state"] == "failed"
    assert failed["finished_at"] is not None
    assert "exit code 23" in failed["error"]
    assert failed["result"] is None
