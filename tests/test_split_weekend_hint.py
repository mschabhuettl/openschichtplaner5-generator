"""Approval hints describe the selected plan without granting permissions."""

from datetime import date

import pytest

from sp5generator.domain import eligibility
from sp5generator.models import Assignment, BoundaryWork, Demand, Objectives
from sp5generator.solver import solve
from sp5generator.validator import validate
from test_core_rules import case, shift


def weekend_case():
    snapshot = case(shifts=[shift("sat", 10, 8, 8), shift("sun", 11, 8, 8)])
    snapshot.shifts[0].name = "Samstagsdienst"
    snapshot.shifts[1].name = "Sonntagsdienst"
    snapshot.positions.append(snapshot.positions[0].model_copy(update={
        "id": "sunday_position", "name": "Funktion Sonntag", "function_id": "sunday",
    }))
    snapshot.demands[1].position_id = "sunday_position"
    snapshot.employees[1].approvals.append(
        snapshot.employees[1].approvals[0].model_copy(update={"function_id": "sunday"})
    )
    # Fixations keep the final split deterministic regardless of objective weights.
    snapshot.assignments = [
        Assignment(employee_id="e0", demand_id="sat", fixed=True),
        Assignment(employee_id="e1", demand_id="sun", fixed=True),
    ]
    snapshot.objectives = Objectives(
        split_weekends=1, hours=0, nights=0, weekends=0, holidays=0,
        wishes=0, changes=0,
    )
    return snapshot


def hints(result):
    return [
        diagnostic for diagnostic in result.validation.diagnostics
        if diagnostic.code == "split_weekend_approval"
    ]


def assert_no_hint(result):
    assert result.validation.valid and result.validation.complete
    assert not hints(result)
    assert result.metrics["split_weekends_blocked_by_approval"] == 0


@pytest.mark.parametrize("partial", [False, True])
def test_missing_approval_reports_exact_person_day_and_duty(partial):
    snapshot = weekend_case()
    original = snapshot.model_dump()
    assert eligibility(snapshot, snapshot.employees[0], snapshot.demands[1]) == ["approval"]

    result = solve(snapshot, time_limit=5, partial=partial)

    hint, = hints(result)
    assert hint.employee_id == "e0"
    assert hint.demand_id == "sun"
    assert hint.date == "2026-01-11"
    assert snapshot.employees[0].name in hint.message
    assert "Sonntagsdienst" in hint.message
    assert "Dienstfreigabe" in hint.message
    assert result.metrics["split_weekends_blocked_by_approval"] == 1
    assert snapshot.model_dump() == original
    assert all(
        not eligibility(snapshot, next(e for e in snapshot.employees if e.id == a.employee_id),
                        next(d for d in snapshot.demands if d.id == a.demand_id))
        for a in result.assignments
    )


def test_eligible_person_on_missing_day_gets_no_approval_hint():
    snapshot = weekend_case()
    snapshot.employees[0].approvals.append(snapshot.employees[1].approvals[1].model_copy())
    assert not eligibility(snapshot, snapshot.employees[0], snapshot.demands[1])

    result = solve(snapshot, time_limit=5)

    assert len({a.employee_id for a in result.assignments}) == 2
    assert_no_hint(result)


def test_missing_approval_and_team_get_no_approval_hint():
    snapshot = weekend_case()
    snapshot.demands[1].team_ids = ["sunday_team"]
    snapshot.employees[1].team_ids.append("sunday_team")
    assert set(eligibility(snapshot, snapshot.employees[0], snapshot.demands[1])) == {
        "approval", "team",
    }

    assert_no_hint(solve(snapshot, time_limit=5))


def test_no_demand_on_missing_day_gets_no_approval_hint():
    snapshot = weekend_case()
    snapshot.demands.pop()
    snapshot.assignments.pop()

    assert_no_hint(solve(snapshot, time_limit=5))


def test_coupled_weekend_gets_no_approval_hint():
    snapshot = weekend_case()
    snapshot.assignments[0].employee_id = "e1"

    result = solve(snapshot, time_limit=5)

    assert {a.employee_id for a in result.assignments} == {"e1"}
    assert_no_hint(result)


def test_disabled_split_weekend_objective_gets_no_approval_hint():
    snapshot = weekend_case()
    snapshot.objectives.split_weekends = 0

    assert_no_hint(solve(snapshot, time_limit=5))


def test_approval_hint_preserves_validity_status_and_selected_plan():
    snapshot = weekend_case()
    enabled = solve(snapshot, time_limit=5)
    independent = validate(snapshot, enabled.assignments)
    snapshot.objectives.split_weekends = 0
    disabled = solve(snapshot, time_limit=5)

    assert len(hints(enabled)) == 1
    assert not hints(disabled)
    assert enabled.validation.valid is disabled.validation.valid is independent.valid is True
    assert enabled.validation.complete is disabled.validation.complete is independent.complete is True
    assert enabled.solver_status == disabled.solver_status == "OPTIMAL"
    assert enabled.assignments == disabled.assignments


def test_metric_counts_both_people_with_only_missing_approvals():
    snapshot = weekend_case()
    snapshot.employees[1].approvals.pop(0)

    result = solve(snapshot, time_limit=5)

    assert result.validation.valid and result.validation.complete
    assert {(hint.employee_id, hint.demand_id, hint.date) for hint in hints(result)} == {
        ("e0", "sun", "2026-01-11"), ("e1", "sat", "2026-01-10"),
    }
    assert len(hints(result)) == result.metrics["split_weekends_blocked_by_approval"] == 2


def test_smallest_reason_set_selects_the_approval_only_demand():
    snapshot = weekend_case()
    snapshot.demands.insert(0, Demand(
        id="other_sunday_team", shift_id="sun", position_id="sunday_position",
        minimum=0, maximum=1, team_ids=["other_team"],
    ))
    assert set(eligibility(snapshot, snapshot.employees[0], snapshot.demands[0])) == {
        "approval", "team",
    }

    result = solve(snapshot, time_limit=5)

    hint, = hints(result)
    assert hint.demand_id == "sun"
    assert result.metrics["split_weekends_blocked_by_approval"] == 1


def test_any_eligible_demand_suppresses_hint_for_the_missing_day():
    snapshot = weekend_case()
    snapshot.demands.append(Demand(
        id="eligible_sunday", shift_id="sun", position_id="p", minimum=0, maximum=1,
    ))
    # The extra demand is individually eligible; the joint day limit keeps the split.
    snapshot.profiles[0].max_work_days = 1
    assert not eligibility(snapshot, snapshot.employees[0], snapshot.demands[-1])

    result = solve(snapshot, time_limit=5)

    assert {(a.employee_id, a.demand_id) for a in result.assignments} == {
        ("e0", "sat"), ("e1", "sun"),
    }
    assert_no_hint(result)


def test_friday_night_touching_saturday_splits_the_weekend():
    snapshot = weekend_case()
    snapshot.shifts[0] = shift("sat", 9, 22, 8, "night")

    result = solve(snapshot, time_limit=5)

    # Der Freitagnachtdienst verbraucht den Samstagmorgen; ohne Sonntag bleibt
    # das Wochenende geteilt, und dafür fehlt e0 die Freigabe.
    hint, = hints(result)
    assert hint.employee_id == "e0"
    assert hint.date == "2026-01-11"
    assert hint.demand_id == "sun"
    assert result.metrics["split_weekends_blocked_by_approval"] == 1


def test_saturday_night_reaching_into_sunday_completes_the_weekend():
    snapshot = weekend_case()
    snapshot.shifts[0] = shift("sat", 10, 22, 8, "night")
    snapshot.shifts[1].segments = shift("sun", 11, 18, 4).segments
    snapshot.shifts[1].paid_minutes = 240

    # Samstag 22 bis Sonntag 06 berührt beide Tage: kein geteiltes Wochenende.
    assert_no_hint(solve(snapshot, time_limit=5))


@pytest.mark.parametrize("day_only", [False, True])
def test_personal_work_counts_as_a_weekend_start(day_only):
    snapshot = weekend_case()
    snapshot.boundary_work = [BoundaryWork(
        id="personal_sat", employee_id="e0", kind="day", in_period=True,
        segments=[] if day_only else snapshot.shifts[0].segments,
        day=date(2026, 1, 10) if day_only else None, paid_minutes=480,
    )]
    snapshot.demands.pop(0)
    snapshot.assignments.pop(0)

    result = solve(snapshot, time_limit=5)

    assert result.validation.valid and result.validation.complete
    hint, = hints(result)
    assert hint.employee_id == "e0"
    assert hint.demand_id == "sun"
    assert hint.date == "2026-01-11"
    assert result.metrics["split_weekends_blocked_by_approval"] == 1


@pytest.mark.parametrize("day_only", [False, True])
def test_personal_work_on_the_other_day_couples_the_weekend(day_only):
    snapshot = weekend_case()
    snapshot.boundary_work = [BoundaryWork(
        id="personal_sun", employee_id="e0", kind="day", in_period=True,
        segments=[] if day_only else snapshot.shifts[1].segments,
        day=date(2026, 1, 11) if day_only else None, paid_minutes=480,
    )]

    assert_no_hint(solve(snapshot, time_limit=5))


@pytest.mark.parametrize("outside_day", ["sat", "sun"])
def test_weekends_with_one_day_outside_the_period_get_no_hint(outside_day):
    snapshot = weekend_case()
    if outside_day == "sat":
        snapshot.period_start = date(2026, 1, 11)
    else:
        snapshot.period_end = date(2026, 1, 10)

    assert_no_hint(solve(snapshot, time_limit=5))


def test_certified_fallback_plan_also_reports_approval_hint(monkeypatch):
    from ortools.sat.python import cp_model

    snapshot = weekend_case()
    for assignment in snapshot.assignments:
        assignment.fixed = False
    original = cp_model.CpSolver.solve

    def stop_after_certificate(self, model, *args, **kwargs):
        if self.parameters.fix_variables_to_their_hinted_value:
            return original(self, model, *args, **kwargs)
        return cp_model.UNKNOWN

    monkeypatch.setattr(cp_model.CpSolver, "solve", stop_after_certificate)

    result = solve(snapshot, time_limit=5, partial=True)

    assert result.solver_status == "FEASIBLE"
    assert result.parameters["warm_start_certificate_status"] == "OPTIMAL"
    assert result.validation.valid and result.validation.complete
    hint, = hints(result)
    assert hint.employee_id == "e0"
    assert hint.demand_id == "sun"
    assert result.metrics["split_weekends_blocked_by_approval"] == 1
