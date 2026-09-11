"""Independent personal boundary work uses the established hard-rule contract."""
from datetime import date

import pytest

from sp5generator.models import Assignment, BoundaryWork, Snapshot
from sp5generator.domain import snapshot_hash
from sp5generator.solver import solve
from sp5generator.validator import validate
from test_boundary_time_contract import boundary_case


def convert(snapshot):
    converted = snapshot.model_copy(deep=True)
    fixed_ids = {a.demand_id for a in converted.assignments}
    demands = {d.id: d for d in converted.demands}
    shifts = {s.id: s for s in converted.shifts}
    for a in converted.assignments:
        s = shifts[demands[a.demand_id].shift_id]
        converted.boundary_work.append(BoundaryWork(
            id=s.id, employee_id=a.employee_id, segments=s.segments, kind=s.kind,
        ))
    converted.assignments = []
    converted.demands = [d for d in converted.demands if d.id not in fixed_ids]
    converted.shifts = [s for s in converted.shifts if s.id not in {w.id for w in converted.boundary_work}]
    return converted


@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("rule", [
    "rest", "daily_limit", "weekly_limit", "consecutive_work", "consecutive_nights",
    "weekly_rest", "period_limit", "interleaving", "night_rest", "overlap",
])
def test_boundary_context_preserves_hard_rules_without_staffing(rule, partial):
    snapshot = convert(boundary_case(rule))
    new_id, = {d.id for d in snapshot.demands}
    proposed = [Assignment(employee_id="e0", demand_id=new_id)]
    checked = validate(snapshot, proposed)
    assert not checked.valid
    assert ("rest" if rule == "night_rest" else rule) in {d.code for d in checked.diagnostics}
    assert validate(snapshot, []).valid
    result = solve(snapshot, 5, partial=partial)
    assert result.solver_status == ("OPTIMAL" if partial else "INFEASIBLE")
    assert not result.assignments
    assert result.vacancies == {new_id: 1}
    if partial:
        assert result.validation.valid and not result.validation.complete


@pytest.mark.parametrize("partial", [False, True])
def test_elapsed_limits_target_and_roundtrip(partial):
    original = boundary_case("weekly_limit")
    original.profiles[0].max_weekly_minutes = 960
    original.shifts[0].paid_minutes = 6000
    original.shifts[1].paid_minutes = 60
    original.employees[0].target_minutes = 60
    snapshot = convert(original)
    assert Snapshot.model_validate_json(snapshot.model_dump_json()) == snapshot
    assert snapshot_hash(snapshot) != snapshot_hash(snapshot.model_copy(update={"boundary_work": []}))
    result = solve(snapshot, 5, partial=partial)
    assert result.validation.complete
    assert len(result.assignments) == 1
    assert result.metrics["employees"]["e0"]["paid_minutes"] == 60
    assert result.metrics["employees"]["e0"]["deviation_minutes"] == 0
    snapshot.profiles[0].max_weekly_minutes = 959
    assert "weekly_limit" in {d.code for d in validate(snapshot, result.assignments).diagnostics}


def test_context_needs_no_historical_approval_team_or_workplace():
    snapshot = convert(boundary_case("weekly_limit"))
    snapshot.profiles[0].max_weekly_minutes = 960
    snapshot.employees[0].approvals[0].valid_from = snapshot.period_start
    result = solve(snapshot, 5)
    assert result.validation.complete
    snapshot.employees[0].approvals = []
    assert "approval" in {d.code for d in validate(snapshot, result.assignments).diagnostics}
    assert solve(snapshot, 5).solver_status == "INFEASIBLE"


@pytest.mark.parametrize("problem,code", [
    ("kind", "boundary_kind"), ("employee", "boundary_reference"),
    ("period", "boundary_period"), ("duplicate", "duplicate_id"),
    ("interval", "interval"), ("context", "context"),
])
def test_invalid_context_is_never_relaxed(problem, code):
    snapshot = convert(boundary_case("rest"))
    work = snapshot.boundary_work[0]
    if problem == "kind":
        work.kind = "unknown"
    elif problem == "employee":
        work.employee_id = "missing"
    elif problem == "period":
        snapshot.period_start = date(2026, 1, 4)
    elif problem == "duplicate":
        snapshot.boundary_work.append(work.model_copy(deep=True))
    elif problem == "interval":
        work.segments = []
    else:
        snapshot.context_start = snapshot.period_start
    for partial in (False, True):
        result = solve(snapshot, 5, partial=partial)
        assert result.solver_status == "MODEL_INVALID"
        assert code in {d.code for d in result.validation.diagnostics}
    assert code in {d.code for d in validate(snapshot, []).diagnostics}


def test_old_fixation_cannot_also_be_boundary_work():
    snapshot = boundary_case("rest")
    snapshot.boundary_work = convert(snapshot).boundary_work
    assert "boundary_duplicate" in {d.code for d in validate(snapshot, snapshot.assignments).diagnostics}
    assert solve(snapshot, 5, partial=True).solver_status == "MODEL_INVALID"


def test_empty_extension_preserves_previous_snapshot_hash():
    import hashlib
    import json
    snapshot = boundary_case("rest")
    legacy = snapshot.model_dump(mode="json", exclude={"boundary_work"})
    expected = hashlib.sha256(json.dumps(legacy, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert snapshot_hash(Snapshot.model_validate(legacy)) == expected


@pytest.mark.parametrize("partial", [False, True])
def test_personal_context_does_not_block_other_employees(partial):
    snapshot = convert(boundary_case("rest"))
    other = snapshot.employees[0].model_copy(deep=True)
    other.id = "other"
    snapshot.employees.append(other)
    result = solve(snapshot, 5, partial=partial)
    assert result.validation.complete
    assert [(a.employee_id, a.demand_id) for a in result.assignments] == [("other", "new")]


def test_http_persistence_and_worker_keep_context(tmp_path):
    import subprocess
    import sys
    from fastapi.testclient import TestClient
    from sp5generator.webapp import create_app
    from sp5generator.jobs import Store

    snapshot = convert(boundary_case("rest"))
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        saved = client.put("/api/snapshots", json=snapshot.model_dump(mode="json"))
        assert saved.status_code == 200
        payload = saved.json()
        assert payload["boundary_work"] == snapshot.model_dump(mode="json")["boundary_work"]
        loaded = client.get("/api/snapshots/" + payload["id"]).json()
        assert loaded == payload
        response = client.post("/api/validate", json={"snapshot": loaded, "assignments": [
            Assignment(employee_id="e0", demand_id="new").model_dump(mode="json")
        ]})
        assert "rest" in {d["code"] for d in response.json()["diagnostics"]}
    store = Store(tmp_path / "worker.sqlite")
    saved = store.save_snapshot(snapshot, "test-owner")
    job = store.submit(saved.id, "test-owner", 5, partial=True)
    worker = subprocess.run([sys.executable, "-m", "sp5generator.cli", "worker", "--store", store.path,
                             "--once"], capture_output=True, text=True, timeout=20)
    assert worker.returncode == 0, worker.stderr
    result = store.get_job(job["id"], "test-owner")
    assert result["state"] == "succeeded"
    assert result["result"]["solver_status"] == "OPTIMAL"
    assert result["result"]["assignments"] == []
    assert result["result"]["validation"]["valid"]


@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("frame", ["rolling_elapsed", "rolling_local"])
def test_rolling_rest_also_reads_personal_context(frame, partial):
    from test_spill_rest import spill_case
    snapshot = convert(spill_case(frame))
    assert "weekly_rest" in {d.code for d in validate(snapshot, [
        Assignment(employee_id="e0", demand_id="spill")
    ]).diagnostics}
    result = solve(snapshot, 5, partial=partial)
    assert result.solver_status == ("OPTIMAL" if partial else "INFEASIBLE")
    assert not result.assignments


@pytest.mark.parametrize("bridge", [False, True])
def test_night_block_context_bridge(bridge):
    from test_core_rules import case, shift
    snapshot = case(1, [shift("a", 5, 22, 8, "night"),
                        shift("b", 6, 22, 8, "night"),
                        shift("c", 7, 22, 8, "night")])
    snapshot.period_start = snapshot.period_end = date(2026, 1, 7)
    snapshot.profiles[0].after_night_block_rest_minutes = 2880
    snapshot.assignments = [Assignment(employee_id="e0", demand_id="a", fixed=True)]
    if bridge:
        snapshot.assignments.append(Assignment(employee_id="e0", demand_id="b", fixed=True))
    else:
        snapshot.shifts = [s for s in snapshot.shifts if s.id != "b"]
        snapshot.demands = [d for d in snapshot.demands if d.id != "b"]
    snapshot = convert(snapshot)
    checked = validate(snapshot, [Assignment(employee_id="e0", demand_id="c")])
    assert checked.complete is bridge
    if not bridge:
        assert "night_block" in {d.code for d in checked.diagnostics}
    result = solve(snapshot, 5)
    assert result.solver_status == ("OPTIMAL" if bridge else "INFEASIBLE")
