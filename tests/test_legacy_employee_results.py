"""Saved results from before Employee.excluded keep their exact input binding."""

import hashlib
import json

import pytest

from sp5generator.cli import main
from sp5generator.domain import snapshot_hash, snapshot_hash_matches
from sp5generator.export import export_table
from sp5generator.jobs import Conflict, Store
from sp5generator.models import Assignment, BoundaryWork, Result, Snapshot
from sp5generator.validator import validate
from test_core_rules import case, shift


def legacy_payload(snapshot):
    payload = snapshot.model_dump(mode="json")
    if not payload["boundary_work"]:
        payload.pop("boundary_work")
    for employee in payload["employees"]:
        employee.pop("excluded")
    return payload


def legacy_result(snapshot):
    digest = hashlib.sha256(json.dumps(
        legacy_payload(snapshot), sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    assignments = [Assignment(employee_id="e0", demand_id="s")]
    validation = validate(snapshot, assignments)
    assert validation.valid and validation.complete
    return Result(
        snapshot_id=snapshot.id, snapshot_hash=digest, solver_status="OPTIMAL",
        assignments=assignments, validation=validation, runtime_seconds=0,
    )


def historical_snapshot():
    snapshot = case(n=1)
    snapshot.boundary_work = [BoundaryWork(
        id="historical-duty", employee_id="e0", kind="day",
        segments=shift("historical-duty", 3, 8, 8).segments,
    )]
    return snapshot


@pytest.mark.parametrize("with_boundary_work", [False, True])
def test_legacy_result_survives_loading_validation_export_and_acceptance(
    tmp_path, with_boundary_work
):
    store = Store(tmp_path / "planning.sqlite3")
    snapshot = store.save_snapshot(
        historical_snapshot() if with_boundary_work else case(n=1), "local-user"
    )
    payload = legacy_payload(snapshot)
    with store.connect() as connection:
        connection.execute("UPDATE snapshots SET payload=? WHERE id=?",
                           (json.dumps(payload), snapshot.id))
    restored = store.get_snapshot(snapshot.id, "local-user")
    result = legacy_result(restored)
    assert restored == snapshot
    assert all(not employee.excluded for employee in restored.employees)
    assert result.snapshot_hash != snapshot_hash(restored)
    assert snapshot_hash_matches(restored, result.snapshot_hash)
    assert snapshot_hash_matches(restored, snapshot_hash(restored))

    direct_export = tmp_path / "direct.csv"
    export_table(restored, result, direct_export)
    assert "Testperson 001" in direct_export.read_text(encoding="utf-8-sig")

    # Opening and serializing adds excluded:false, without changing the input's
    # meaning or invalidating its earlier saved result.
    source, proposal = tmp_path / "input.json", tmp_path / "result.json"
    source.write_text(restored.model_dump_json(), encoding="utf-8")
    proposal.write_text(result.model_dump_json(), encoding="utf-8")
    checked = tmp_path / "validation.json"
    assert main(["validate", str(source), str(proposal), "-o", str(checked)]) == 0
    assert json.loads(checked.read_text(encoding="utf-8"))["complete"]
    cli_export = tmp_path / "cli.csv"
    assert main(["export", str(source), str(proposal), str(cli_export)]) == 0
    assert cli_export.read_bytes() == direct_export.read_bytes()

    job = store.submit(snapshot.id, "local-user", 5)
    assert store.get_job_snapshot(job["id"], "local-user") == restored
    with store.connect() as connection:
        connection.execute("UPDATE jobs SET state='succeeded',result=? WHERE id=?",
                           (result.model_dump_json(), job["id"]))
    assert store.apply_synthetic(job["id"], "local-user", "legacy-result")["status"] == "applied"


@pytest.mark.parametrize("change", ["excluded", "target", "approval", "history", "metadata"])
def test_legacy_result_still_rejects_changed_snapshot(tmp_path, capsys, change):
    store = Store(tmp_path / "planning.sqlite3")
    snapshot = store.save_snapshot(historical_snapshot(), "local-user")
    result = legacy_result(snapshot)
    changed = Snapshot.model_validate(legacy_payload(snapshot))
    if change == "excluded":
        changed.employees[0].excluded = True
    elif change == "target":
        changed.employees[0].target_minutes += 60
    elif change == "approval":
        changed.employees[0].approvals = []
    elif change == "history":
        changed.boundary_work = []
    else:
        changed.metadata["project_name"] = "Changed synthetic project"
    assert not snapshot_hash_matches(changed, result.snapshot_hash)
    assert snapshot_hash_matches(changed, snapshot_hash(changed))

    output = tmp_path / "existing.csv"
    output.write_text("existing export", encoding="utf-8")
    with pytest.raises(ValueError, match="does not reference this snapshot"):
        export_table(changed, result, output)
    assert output.read_text(encoding="utf-8") == "existing export"

    source, proposal = tmp_path / "input.json", tmp_path / "result.json"
    source.write_text(changed.model_dump_json(), encoding="utf-8")
    proposal.write_text(result.model_dump_json(), encoding="utf-8")
    assert main(["validate", str(source), str(proposal), "-o", str(output)]) == 2
    assert output.read_text(encoding="utf-8") == "existing export"
    assert "does not reference this snapshot" in capsys.readouterr().err

    job = store.submit(snapshot.id, "local-user", 5)
    # Even when current and job snapshots agree, an old result must not match
    # an edited input through the compatibility path.
    with store.connect() as connection:
        connection.execute("UPDATE snapshots SET payload=? WHERE id=?",
                           (changed.model_dump_json(), snapshot.id))
        connection.execute(
            "UPDATE jobs SET state='succeeded',payload=?,result=? WHERE id=?",
            (changed.model_dump_json(), result.model_dump_json(), job["id"]),
        )
    with pytest.raises(Conflict, match="different snapshot"):
        store.apply_synthetic(job["id"], "local-user", "legacy-result")
    with store.connect() as connection:
        for table in ("accepted", "receipts", "audit"):
            assert connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
