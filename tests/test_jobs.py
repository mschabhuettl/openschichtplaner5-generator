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
