"""Persistence upgrades, concurrent edits and bounded project/job summaries."""

from concurrent.futures import ThreadPoolExecutor
import contextlib
import json
import sqlite3

import pytest

from sp5generator.demo import make_demo
from sp5generator.jobs import Conflict, Store


def legacy_store(path):
    snapshot = make_demo(days=1)
    snapshot.revision = "7"
    snapshot.metadata["project_name"] = "January planning"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE snapshots(id TEXT PRIMARY KEY,owner TEXT NOT NULL,revision INTEGER NOT NULL,payload TEXT NOT NULL)")
        connection.execute("INSERT INTO snapshots VALUES(?,?,?,?)",
                           (snapshot.id, "local-user", 7, snapshot.model_dump_json()))
    return snapshot


def test_legacy_migration_is_concurrent_idempotent_and_keeps_payload(tmp_path):
    path = tmp_path / "planning.sqlite3"
    original = legacy_store(path)
    with ThreadPoolExecutor(max_workers=4) as pool:
        stores = list(pool.map(lambda _: Store(path), range(4)))
    for store in stores:
        assert store.get_snapshot(original.id, "local-user") == original
        summary, = store.list_snapshots("local-user")
        assert summary["project_name"] == "January planning"
        assert summary["revision"] == 7
        assert summary["employee_count"] == len(original.employees)
        assert summary["shift_count"] == len(original.shifts)
        assert summary["demand_count"] == len(original.demands)
        assert summary["updated_at"] == original.created_at.timestamp()
        assert not summary["archived"]
    changed = original.model_copy(deep=True)
    changed.metadata["project_name"] = "Revised project"
    saved = stores[0].save_snapshot(changed, "local-user")
    assert saved.revision == "8"
    assert Store(path).list_snapshots("local-user")[0]["project_name"] == "Revised project"


def test_failed_migration_rolls_back_and_can_be_retried(tmp_path):
    path = tmp_path / "planning.sqlite3"
    original = legacy_store(path)
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TRIGGER fail_migration BEFORE UPDATE ON snapshots BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
    with pytest.raises(sqlite3.IntegrityError, match="synthetic failure"):
        Store(path)
    with sqlite3.connect(path) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(snapshots)")]
        assert columns == ["id", "owner", "revision", "payload"]
        connection.execute("DROP TRIGGER fail_migration")
    assert Store(path).get_snapshot(original.id, "local-user") == original


def test_legacy_unrestricted_project_name_does_not_block_upgrade(tmp_path):
    path = tmp_path / "planning.sqlite3"
    original = legacy_store(path)
    original.metadata["project_name"] = {"old": "unrestricted metadata"}
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE snapshots SET payload=?", (original.model_dump_json(),))
    store = Store(path)
    assert store.list_snapshots("local-user")[0]["project_name"] == ""
    assert store.get_snapshot(original.id, "local-user") == original


def test_summaries_never_read_personnel_payload_or_large_results(tmp_path, monkeypatch):
    store = Store(tmp_path / "planning.sqlite3")
    snapshot = store.save_snapshot(make_demo(days=1), "local-user")
    first = store.submit(snapshot.id, "local-user")
    second = store.submit(snapshot.id, "local-user")
    with store.connect() as connection:
        connection.execute("UPDATE jobs SET result=? WHERE id=?",
                           (json.dumps({"large": "x" * 1_000_000}), first["id"]))
    original_connect = store.connect

    @contextlib.contextmanager
    def summaries_only():
        with original_connect() as connection:
            def authorize(action, table, column, *_):
                if action == sqlite3.SQLITE_READ and table in {"snapshots", "jobs"} and column in {"payload", "result"}:
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK
            connection.set_authorizer(authorize)
            yield connection

    monkeypatch.setattr(store, "connect", summaries_only)
    assert store.list_snapshots("local-user")[0]["id"] == snapshot.id
    assert store.get_job_status(first["id"], "local-user")["queue_position"] == 1
    assert store.get_job_status(second["id"], "local-user")["queue_position"] == 2
    assert len(store.list_jobs("local-user")) == 2
    with pytest.raises(KeyError):
        store.get_job_status(first["id"], "another-user")


def test_project_recency_pagination_and_concurrent_revision_guard(tmp_path):
    store = Store(tmp_path / "planning.sqlite3")
    first = store.save_snapshot(make_demo(days=1), "local-user")
    second = make_demo(days=2)
    second.id = "second-project"
    second = store.save_snapshot(second, "local-user")
    assert [row["id"] for row in store.list_snapshots("local-user")] == [second.id, first.id]
    assert store.list_snapshots("local-user", limit=1, offset=1)[0]["id"] == first.id

    def save(_):
        try:
            return store.save_snapshot(first, "local-user").revision
        except Conflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(save, range(2))) == ["2", "conflict"]
    assert store.list_snapshots("local-user")[0]["id"] == first.id


def test_copy_archive_and_restore_preserve_calculation_history(tmp_path):
    store = Store(tmp_path / "planning.sqlite3")
    original = store.save_snapshot(make_demo(days=1), "local-user")
    job = store.submit(original.id, "local-user")
    with pytest.raises(Conflict, match="Berechnung"):
        store.set_archived(original.id, "local-user", original.revision, True)
    store.cancel(job["id"], "local-user")
    archived = store.set_archived(original.id, "local-user", original.revision, True)
    assert archived.revision == "2"
    assert store.list_snapshots("local-user") == []
    assert store.list_snapshots("local-user", archived=True)[0]["id"] == original.id
    assert store.get_job_snapshot(job["id"], "local-user") == original
    with pytest.raises(Conflict):
        store.submit(original.id, "local-user")
    with pytest.raises(Conflict):
        store.copy_snapshot(original.id, "local-user", original.revision)
    with pytest.raises(KeyError):
        store.set_archived(original.id, "another-user", archived.revision, False)
    copied = store.copy_snapshot(original.id, "local-user", archived.revision, "Alternative planning")
    assert copied.id != original.id and copied.revision == "1"
    assert copied.metadata["project_name"] == "Alternative planning"
    assert copied.employees == original.employees
    assert store.list_jobs("local-user", snapshot_id=copied.id) == []
    assert store.list_snapshots("local-user")[0]["id"] == copied.id
    restored = store.set_archived(original.id, "local-user", archived.revision, False)
    assert restored.revision == "3"
    assert store.list_snapshots("local-user", archived=True) == []
    assert len(store.list_snapshots("local-user")) == 2


@pytest.mark.parametrize("limit,offset", [(0, 0), (1001, 0), (True, 0), (20, -1), (20, True), (20, 10**100)])
def test_project_list_bounds(tmp_path, limit, offset):
    store = Store(tmp_path / "planning.sqlite3")
    with pytest.raises(ValueError):
        store.list_snapshots("local-user", limit=limit, offset=offset)
