"""Synthetic regressions for the six independently reviewed core contracts."""

from collections import Counter
from datetime import UTC, date, datetime, timedelta
from itertools import permutations
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from sp5generator.domain import input_diagnostics, night_block_conflict, staffing_gaps
from sp5generator.models import Assignment, BoundaryWork, Demand, Objectives
from sp5generator.solver import solve
from sp5generator.validator import PreparedValidator, validate
from sp5generator.webapp import create_app
from test_core_rules import case, shift


def snapshot_for(shifts=None, people=1):
    snapshot = case(n=people, shifts=shifts)
    snapshot.objectives = Objectives(
        hours=0, changes=0, nights=0, weekends=0, holidays=0, wishes=0,
    )
    return snapshot


def assigned(demand_id="s", employee_id="e0", **kwargs):
    return Assignment(employee_id=employee_id, demand_id=demand_id, **kwargs)


@pytest.fixture
def validation_client(tmp_path):
    # In-process HTTP, a private synthetic store, and no worker or live services.
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        yield client


def checked_through_http(client, snapshot, plan):
    checked = validate(snapshot, plan)
    assert PreparedValidator(snapshot).validate(plan) == checked
    response = client.post("/api/validate", json={
        "snapshot": snapshot.model_dump(mode="json"),
        "assignments": [a.model_dump(mode="json") for a in plan],
    })
    assert response.status_code == 200
    payload = response.json()
    assert {key: payload[key] for key in ("valid", "complete", "diagnostics")} == checked.model_dump(mode="json")
    return checked


@pytest.mark.parametrize("cap,accepted", [(0, False), (479, False), (480, True), (None, True)])
def test_core_001_personal_cap_manual_http_and_solver(validation_client, cap, accepted):
    snapshot = snapshot_for()
    snapshot.employees[0].max_period_minutes = cap
    assert input_diagnostics(snapshot) == []

    checked = checked_through_http(validation_client, snapshot, [assigned()])
    assert checked.valid is accepted
    assert checked.complete is accepted
    cap_errors = [d for d in checked.diagnostics if d.code == "personal_period_limit"]
    assert [d.employee_id for d in cap_errors] == ([] if accepted else ["e0"])

    full = solve(snapshot, time_limit=3)
    assert full.solver_status == ("OPTIMAL" if accepted else "INFEASIBLE")
    partial = solve(snapshot, time_limit=3, partial=True)
    assert partial.validation.valid
    assert partial.validation.complete is accepted
    assert len(partial.assignments) == int(accepted)
    assert sum(partial.vacancies.values()) == int(not accepted)


@pytest.mark.parametrize("timed", [False, True])
@pytest.mark.parametrize("cap,accepted", [(479, False), (480, True)])
def test_core_001_personal_cap_counts_paid_boundary_work(timed, cap, accepted):
    snapshot = snapshot_for()
    # Paid minutes, not elapsed minutes, consume the employee's own cap.
    snapshot.shifts[0].paid_minutes = 240
    snapshot.employees[0].max_period_minutes = cap
    snapshot.boundary_work = [
        BoundaryWork(
            id="personal", employee_id="e0", paid_minutes=240, in_period=True,
            segments=shift("personal", 6, 8, 1).segments if timed else [],
            day=None if timed else date(2026, 1, 6),
            kind="day" if timed else "unknown",
        ),
        BoundaryWork(
            id="outside", employee_id="e0", paid_minutes=9000, kind="day",
            segments=shift("outside", 3, 8, 1).segments,
        ),
    ]
    assert input_diagnostics(snapshot) == []
    checked = validate(snapshot, [assigned()])
    assert checked.valid is accepted
    assert ("personal_period_limit" in {d.code for d in checked.diagnostics}) is (not accepted)
    assert solve(snapshot, time_limit=3).solver_status == (
        "OPTIMAL" if accepted else "INFEASIBLE"
    )
    partial = solve(snapshot, time_limit=3, partial=True)
    assert partial.validation.valid
    assert partial.validation.complete is accepted
    assert partial.metrics["employees"]["e0"]["paid_minutes"] == (480 if accepted else 240)


@pytest.mark.parametrize("credit,balance", [(0, -480), (480, -960), (9000, 9000)])
def test_core_001_personal_cap_cannot_be_offset_by_account_balance(credit, balance):
    snapshot = snapshot_for()
    employee = snapshot.employees[0]
    employee.max_period_minutes = 0
    employee.credit_minutes, employee.balance_minutes = credit, balance
    # A permissive profile does not replace the employee's stricter paid cap.
    snapshot.profiles[0].max_period_minutes = 10000
    checked = validate(snapshot, [assigned()])
    assert not checked.valid and not checked.complete
    assert [d.code for d in checked.diagnostics] == ["personal_period_limit"]


def test_core_001_cap_uses_duty_start_day_not_spill_minutes():
    snapshot = snapshot_for([shift("s", 5, 23, 2)])
    snapshot.period_end = snapshot.period_start
    snapshot.shifts[0].paid_minutes = 120
    snapshot.employees[0].max_period_minutes = 119
    checked = validate(snapshot, [assigned()])
    assert not checked.valid
    assert [d.code for d in checked.diagnostics] == ["personal_period_limit"]
    snapshot.employees[0].max_period_minutes = 120
    assert validate(snapshot, [assigned()]).complete
    assert solve(snapshot, time_limit=3).validation.complete


def night_block_snapshot(fold=False):
    snapshot = snapshot_for([
        shift("early", 5, 0, 1, "night"),
        shift("late", 5, 22, 1, "night"),
        shift("next", 7, 0, 1, "night"),
    ])
    actual_rest = 1500
    if fold:
        snapshot.timezone = "Europe/Berlin"
        snapshot.period_start, snapshot.period_end = date(2026, 10, 25), date(2026, 10, 27)
        snapshot.context_start, snapshot.context_end = date(2026, 10, 15), date(2026, 11, 6)
        profile = snapshot.profiles[0]
        profile.valid_from, profile.valid_until = snapshot.context_start, snapshot.context_end
        profile.min_rest_minutes = 0
        employee = snapshot.employees[0]
        employee.employment_start, employee.employment_end = snapshot.context_start, snapshot.context_end
        employee.approvals[0].valid_from = snapshot.context_start
        employee.approvals[0].valid_until = snapshot.context_end
        tz = ZoneInfo(snapshot.timezone)
        for duty, day, fold_number in zip(snapshot.shifts, (25, 25, 27), (0, 1, 0)):
            start = datetime(2026, 10, day, 2, 10 if day == 25 else 0, tzinfo=tz, fold=fold_number)
            duty.segments[0].start = start
            duty.segments[0].end = (start.astimezone(UTC) + timedelta(minutes=10)).astimezone(tz)
            duty.paid_minutes = 10
        actual_rest = 2860
    return snapshot, actual_rest


@pytest.mark.parametrize("order", list(permutations(("early", "late", "next"))))
@pytest.mark.parametrize("fold", [False, True], ids=["same-local-day", "dst-fold"])
@pytest.mark.parametrize("extra_rest", [0, 60], ids=["exact-rest", "short-rest"])
def test_core_002_night_block_order_is_invariant(validation_client, order, fold, extra_rest):
    snapshot, actual_rest = night_block_snapshot(fold)
    snapshot.profiles[0].after_night_block_rest_minutes = actual_rest + extra_rest
    assert input_diagnostics(snapshot) == []
    checked = checked_through_http(validation_client, snapshot, [assigned(d) for d in order])
    assert checked.valid is (extra_rest == 0)
    assert checked.complete is (extra_rest == 0)
    assert [(d.code, d.employee_id, d.demand_id) for d in checked.diagnostics] == (
        [("night_block", "e0", "next")] if extra_rest else []
    )
    full = solve(snapshot, time_limit=3)
    assert full.solver_status == ("INFEASIBLE" if extra_rest else "OPTIMAL")


def test_core_002_untimed_work_cannot_bridge_a_timed_night_block(validation_client):
    snapshot, _ = night_block_snapshot()
    snapshot.profiles[0].after_night_block_rest_minutes = 1560
    snapshot.boundary_work = [BoundaryWork(
        id="untimed", employee_id="e0", segments=[], day=date(2026, 1, 6),
        in_period=True,
    )]
    assert input_diagnostics(snapshot) == []
    checked = checked_through_http(
        validation_client, snapshot, [assigned(d) for d in ("late", "early", "next")],
    )
    assert not checked.valid and not checked.complete
    assert [d.code for d in checked.diagnostics] == ["night_block"]


@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("kind", ["unknown", "day", "night"])
@pytest.mark.parametrize("day", [5, 6], ids=["same-day-blocked", "other-day-allowed"])
def test_core_003_untimed_work_with_night_rule_keeps_day_and_paid_contract(partial, kind, day):
    snapshot = snapshot_for()
    snapshot.profiles[0].after_night_block_rest_minutes = 1440
    snapshot.boundary_work = [BoundaryWork(
        id="untimed", employee_id="e0", segments=[], day=date(2026, 1, day),
        kind=kind, in_period=True, paid_minutes=120,
    )]
    assert input_diagnostics(snapshot) == []
    original = snapshot.model_dump(mode="json")
    checked = validate(snapshot, [assigned()])
    assert checked.valid is (day == 6)
    result = solve(snapshot, time_limit=3, partial=partial)
    assert snapshot.model_dump(mode="json") == original  # No invented timestamps.
    if day == 5 and not partial:
        assert result.solver_status == "INFEASIBLE"
    else:
        assert result.solver_status == "OPTIMAL"
        assert result.validation.valid
        assert result.validation.complete is (day == 6)
        assert len(result.assignments) == int(day == 6)
        assert result.metrics["employees"]["e0"]["paid_minutes"] == (600 if day == 6 else 120)


@pytest.mark.parametrize("untimed_left", [False, True])
def test_core_003_night_block_predicate_does_not_invent_missing_times(untimed_left):
    snapshot = snapshot_for()
    snapshot.profiles[0].after_night_block_rest_minutes = 1440
    untimed = BoundaryWork(
        id="untimed", employee_id="e0", segments=[], day=date(2026, 1, 6),
        kind="night", in_period=True,
    )
    timed = shift("night", 5, 22, 1, "night")
    left, right = (untimed, timed) if untimed_left else (timed, untimed)
    assert night_block_conflict(snapshot, snapshot.employees[0], left, right) is False


@pytest.mark.parametrize("partial", [False, True])
def test_core_003_untimed_work_cannot_relax_timed_block_rest(partial):
    snapshot, _ = night_block_snapshot()
    snapshot.profiles[0].after_night_block_rest_minutes = 1560
    snapshot.boundary_work = [BoundaryWork(
        id="untimed", employee_id="e0", segments=[], day=date(2026, 1, 6), in_period=True,
    )]
    result = solve(snapshot, time_limit=3, partial=partial)
    if partial:
        assert result.solver_status == "OPTIMAL" and result.validation.valid
        assert len(result.assignments) == 2
        assert sum(result.vacancies.values()) == 1
    else:
        assert result.solver_status == "INFEASIBLE"


def alternative_snapshot(groups, people=1):
    snapshot = snapshot_for([
        shift("long", 5, 18, 12, "night"), shift("short", 5, 20, 10, "night"),
    ], people=people)
    for demand, group in zip(snapshot.demands, groups):
        demand.alternative_group = group
    return snapshot


@pytest.mark.parametrize("groups,grouped", [
    ((None, None), False), (("", ""), False), (("post", "post"), True),
    ((" ", " "), True), (("post", " post"), False), ((None, "long"), False),
])
@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("people", [1, 2])
def test_core_004_group_coverage_agrees_across_layers(validation_client, groups, grouped, partial, people):
    snapshot = alternative_snapshot(groups, people)
    assert input_diagnostics(snapshot) == []
    manual = checked_through_http(validation_client, snapshot, [assigned("long")])
    assert manual.valid
    assert manual.complete is grouped
    assert sum(staffing_gaps(snapshot, {"long": 1}).values()) == int(not grouped)

    result = solve(snapshot, time_limit=3, partial=partial)
    feasible = grouped or people == 2 or partial
    if not feasible:
        assert result.solver_status == "INFEASIBLE"
        assert not result.validation.valid and not result.validation.complete
        return
    assert result.solver_status == "OPTIMAL"
    expected_gap = int(not grouped and people == 1)
    assert result.validation.valid
    assert result.validation.complete is (expected_gap == 0)
    assert sum(result.vacancies.values()) == result.metrics["vacancy_count"] == expected_gap
    assert result.vacancies == {
        did: n for did, n in staffing_gaps(snapshot, Counter(a.demand_id for a in result.assignments)).items() if n
    }
    assert validate(snapshot, result.assignments).complete is (expected_gap == 0)
    if partial:
        assert result.parameters["quality_coverage_count"] == expected_gap
    assert [d.alternative_group for d in snapshot.demands] == list(groups)


def test_core_004_full_plan_safety_net_rejects_remaining_vacancies(monkeypatch):
    import sp5generator.solver as solver_module

    snapshot = alternative_snapshot(("", ""))
    # Inject only the original model-grouping defect. CP-SAT and the independent
    # validator remain real: the defense must never publish its incomplete plan.
    monkeypatch.setattr(solver_module, "staffing_groups", lambda s: {"": s.demands})
    result = solve(snapshot, time_limit=3)
    assert result.solver_status == "INFEASIBLE"
    assert result.assignments == []
    assert not result.validation.valid and not result.validation.complete
    assert not any(t["accepted"] for t in result.parameters["search_trace"])


@pytest.mark.parametrize("staffed", [0, 1, 2], ids=["open", "partly-covered", "covered"])
def test_core_005_certified_warm_fallback_counts_group_vacancies(monkeypatch, staffed):
    from ortools.sat.python import cp_model

    snapshot = alternative_snapshot(("post", "post"), people=2)
    for demand in snapshot.demands:
        demand.minimum = demand.maximum = 2
    # A separate saved assignment enables certification even with an empty group.
    snapshot.shifts.append(shift("anchor", 7, 8, 1))
    snapshot.demands.append(Demand(
        id="anchor", shift_id="anchor", position_id="p", minimum=1, maximum=1,
    ))
    snapshot.assignments = [assigned("anchor")] + [
        assigned("long", f"e{i}") for i in range(staffed)
    ]
    assert validate(snapshot, snapshot.assignments).valid
    original = cp_model.CpSolver.solve
    calls, certificate_statuses = [], []

    def certificate_then_unknown(self, model, *args, **kwargs):
        is_certificate = bool(self.parameters.fix_variables_to_their_hinted_value)
        calls.append(is_certificate)
        if is_certificate:
            status = original(self, model, *args, **kwargs)
            certificate_statuses.append(self.status_name(status))
            return status
        # Deterministic timeout seam only; model, certificate and validation are real.
        return cp_model.UNKNOWN

    monkeypatch.setattr(cp_model.CpSolver, "solve", certificate_then_unknown)
    result = solve(snapshot, time_limit=3, partial=True)
    assert calls == [True, False]
    assert certificate_statuses == ["OPTIMAL"]
    assert result.parameters["warm_start_certificate_status"] == "OPTIMAL"
    assert result.parameters["last_optimization_status"] == "UNKNOWN"
    assert result.solver_status == "FEASIBLE"
    assert result.validation.valid
    assert result.validation.complete is (staffed == 2)
    assert result.vacancies == ({"long": 2 - staffed} if staffed < 2 else {})
    assert result.metrics["vacancy_count"] == sum(result.vacancies.values()) == 2 - staffed
    assert result.metrics["objective_phase"] == "vacancies"
    assert result.objective_value == 2 - staffed
    assert result.best_bound is None
    assert not any(a.fixed for a in result.assignments)
    assert validate(snapshot, result.assignments).complete is (staffed == 2)


def late_split_snapshot(tail_days=(8, 9, 10)):
    duty = shift("split", 5, 8, 1)
    duty.segments.extend(shift(f"part-{day}", day, 8, 1).segments[0] for day in tail_days)
    snapshot = snapshot_for([duty])
    snapshot.period_end = snapshot.period_start
    snapshot.profiles[0].max_consecutive_work_days = 2
    return snapshot


@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("source", ["split-parts", "following-context", "personal-work"])
def test_core_006_selected_late_parts_activate_series_windows(validation_client, partial, source):
    snapshot = late_split_snapshot((10,) if source == "following-context" else (8, 9, 10))
    plan = [assigned("split")]
    if source == "following-context":
        snapshot.boundary_work = [BoundaryWork(
            id=f"context-{day}", employee_id="e0", kind="day",
            segments=shift(f"context-{day}", day, 8, 1).segments,
        ) for day in (11, 12)]
    elif source == "personal-work":
        snapshot.boundary_work = [BoundaryWork(
            id="personal", employee_id="e0", kind="day", in_period=True,
            segments=snapshot.shifts[0].segments,
        )]
        snapshot.shifts, snapshot.demands, plan = [], [], []
    assert input_diagnostics(snapshot) == []
    checked = checked_through_http(validation_client, snapshot, plan)
    assert not checked.valid and not checked.complete
    assert [(d.code, d.employee_id, d.date) for d in checked.diagnostics] == [
        ("consecutive_work", "e0", "2026-01-12" if source == "following-context" else "2026-01-10"),
    ]
    result = solve(snapshot, time_limit=3, partial=partial)
    if not partial or source == "personal-work":
        assert result.solver_status == "INFEASIBLE"
        # The model must enforce this, not discover it only by validator cuts.
        assert result.parameters["search_trace"][0]["native_status"] == "INFEASIBLE"
    else:
        assert result.solver_status == "OPTIMAL"
        assert result.assignments == []
        assert result.validation.valid and not result.validation.complete
        assert result.vacancies == {"split": 1}
        assert result.metrics["separation_rounds"] == 0


@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("selected", [False, True])
def test_core_006_only_selected_tail_extends_required_context(partial, selected):
    snapshot = late_split_snapshot((10,))
    snapshot.context_end = date(2026, 1, 11)  # Need Jan 12 only if the late part is chosen.
    snapshot.demands[0].minimum = snapshot.demands[0].maximum = int(selected)
    plan = [assigned("split")] if selected else []
    assert input_diagnostics(snapshot) == []
    checked = validate(snapshot, plan)
    assert checked.valid
    assert checked.complete is (not selected)
    assert {d.code for d in checked.diagnostics} == ({"context"} if selected else set())
    result = solve(snapshot, time_limit=3, partial=partial)
    assert result.solver_status == "OPTIMAL"
    assert result.validation.valid
    assert result.validation.complete is (not selected)
    assert len(result.assignments) == int(selected)


@pytest.mark.parametrize("partial", [False, True])
def test_core_006_unselected_candidate_does_not_activate_future_context_violation(partial):
    snapshot = late_split_snapshot((10,))
    snapshot.demands[0].minimum = snapshot.demands[0].maximum = 0
    snapshot.shifts.append(shift("required", 5, 8, 1))
    snapshot.demands.append(Demand(
        id="required", shift_id="required", position_id="p", minimum=1, maximum=1,
    ))
    snapshot.boundary_work = [BoundaryWork(
        id=f"context-{day}", employee_id="e0", kind="day",
        segments=shift(f"context-{day}", day, 12, 1).segments,
    ) for day in (10, 11, 12)]
    assert input_diagnostics(snapshot) == []
    assert validate(snapshot, [assigned("required")]).complete
    result = solve(snapshot, time_limit=3, partial=partial)
    assert result.solver_status == "OPTIMAL"
    assert result.validation.valid and result.validation.complete
    assert [a.demand_id for a in result.assignments] == ["required"]


def test_core_006_late_night_parts_do_not_create_new_night_start_days():
    snapshot = late_split_snapshot((10,))
    snapshot.shifts[0].kind = "night"
    snapshot.profiles[0].max_consecutive_work_days = None
    snapshot.profiles[0].max_consecutive_nights = 1
    snapshot.boundary_work = [BoundaryWork(
        id=f"context-{day}", employee_id="e0", kind="night",
        segments=shift(f"context-{day}", day, 8, 1, "night").segments,
    ) for day in (11, 12)]
    assert validate(snapshot, [assigned("split")]).complete
    result = solve(snapshot, time_limit=3)
    assert result.solver_status == "OPTIMAL" and result.validation.complete
