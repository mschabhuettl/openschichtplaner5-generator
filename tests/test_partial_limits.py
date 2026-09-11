"""Synthetic counterexamples for the reported 0.9.29 partial-plan symptoms.

No customer snapshot is used. Expected elapsed totals are stated explicitly,
not obtained from the solver's daily-minute helper.
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from ortools.sat.python import cp_model

from sp5generator import solver
from sp5generator.models import Assignment, Interval
from sp5generator.timeutils import localize
from sp5generator.validator import validate
from test_core_rules import case, shift


def plan(snapshot):
    return [Assignment(employee_id="e0", demand_id=d.id) for d in snapshot.demands]


@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("limit,expected_count", [(479, 0), (480, 1), (960, 2)])
def test_daily_limit_sums_separate_duties_not_paid_minutes(partial, limit, expected_count):
    snapshot = case(1, [shift("morning", 5, 0, 8), shift("evening", 5, 16, 8)])
    snapshot.profiles[0].min_rest_minutes = 0
    snapshot.profiles[0].max_daily_minutes = limit
    # Each duty pays just one hour; the hard cap counts eight elapsed hours.
    for duty in snapshot.shifts:
        duty.paid_minutes = 60
    checked = validate(snapshot, plan(snapshot))
    assert checked.valid is (expected_count == 2)
    if expected_count < 2:
        assert "daily_limit" in {d.code for d in checked.diagnostics}
    result = solver.solve(snapshot, 3, partial=partial)
    if not partial and expected_count < 2:
        assert result.solver_status == "INFEASIBLE"
    else:
        assert result.solver_status == "OPTIMAL"
        assert len(result.assignments) == expected_count
        assert validate(snapshot, result.assignments).valid
        assert sum(result.vacancies.values()) == 2 - expected_count


@pytest.mark.parametrize("partial", [False, True])
def test_weekly_limit_uses_fixed_context_and_not_target_or_paid_minutes(partial):
    snapshot = case(1, [shift("boundary", 5, 8, 8), shift("new", 7, 8, 8)])
    snapshot.period_start = date(2026, 1, 7)
    snapshot.profiles[0].max_weekly_minutes = 15 * 60
    snapshot.employees[0].target_minutes = 100 * 60
    snapshot.shifts[0].paid_minutes = snapshot.shifts[1].paid_minutes = 60
    snapshot.assignments = [Assignment(employee_id="e0", demand_id="boundary", fixed=True)]
    checked = validate(snapshot, plan(snapshot))
    assert not checked.valid
    assert "weekly_limit" in {d.code for d in checked.diagnostics}
    result = solver.solve(snapshot, 3, partial=partial)
    if partial:
        assert result.solver_status == "OPTIMAL"
        assert [(a.demand_id, a.fixed) for a in result.assignments] == [("boundary", True)]
        assert result.vacancies == {"new": 1}
        assert validate(snapshot, result.assignments).valid
    else:
        assert result.solver_status == "INFEASIBLE"


@pytest.mark.parametrize("maximum,expected", [(None, 3), (40 * 60, 1)])
def test_24_hour_duties_are_not_forbidden_by_11_36_rest_alone(maximum, expected):
    snapshot = case(1, [shift("a", 5, 0, 24), shift("b", 7, 0, 24), shift("c", 9, 0, 24)])
    profile = snapshot.profiles[0]
    profile.min_rest_minutes = 660
    profile.weekly_rest_minutes = 2160
    profile.max_weekly_minutes = maximum
    snapshot.employees[0].target_minutes = 40 * 60
    # 72h elapsed, 24h paid, 40h target. All three quantities differ.
    for duty in snapshot.shifts:
        duty.paid_minutes = 8 * 60
    result = solver.solve(snapshot, 3, partial=True)
    assert result.solver_status == "OPTIMAL"
    assert len(result.assignments) == expected
    assert validate(snapshot, result.assignments).valid
    assert result.metrics["employees"]["e0"]["paid_minutes"] == expected * 480


@pytest.mark.parametrize("daily_limit,accepted", [(719, False), (720, True)])
def test_daily_limit_is_not_a_single_duty_length_limit(daily_limit, accepted):
    snapshot = case(1, [shift("noon_to_noon", 5, 12, 24)])
    snapshot.profiles[0].min_rest_minutes = 660
    snapshot.profiles[0].weekly_rest_minutes = 2160
    snapshot.profiles[0].max_daily_minutes = daily_limit
    # Noon to noon is 12h on each local calendar day, not 24h on one day.
    assert validate(snapshot, plan(snapshot)).valid is accepted
    result = solver.solve(snapshot, 3, partial=True)
    assert len(result.assignments) == int(accepted)
    assert result.validation.valid


@pytest.mark.parametrize("kind", ["overlap", "rest", "same_shift"])
def test_partial_never_keeps_conflicting_assignments(kind):
    snapshot = case(1, [shift("a", 5, 8, 8), shift("b", 5, 16, 8)])
    snapshot.profiles[0].min_rest_minutes = 660
    if kind == "overlap":
        snapshot.shifts[1] = shift("b", 5, 12, 8)
    elif kind == "same_shift":
        snapshot.demands[1].shift_id = "a"
    assert not validate(snapshot, plan(snapshot)).valid
    result = solver.solve(snapshot, 3, partial=True)
    assert len(result.assignments) == 1
    assert validate(snapshot, result.assignments).valid


def dated_case(start, end, intervals):
    snapshot = case(1, [shift(str(i), 5, 0, 1) for i in range(len(intervals))])
    snapshot.timezone = "Europe/Vienna"
    snapshot.period_start, snapshot.period_end = start, end
    snapshot.context_start, snapshot.context_end = start - timedelta(days=14), end + timedelta(days=14)
    profile = snapshot.profiles[0]
    profile.valid_from, profile.valid_until = snapshot.context_start, snapshot.context_end
    employee = snapshot.employees[0]
    employee.employment_start, employee.employment_end = profile.valid_from, profile.valid_until
    employee.approvals[0].valid_from, employee.approvals[0].valid_until = profile.valid_from, profile.valid_until
    for duty, (a, b) in zip(snapshot.shifts, intervals):
        duty.segments = [Interval(start=a, end=b)]
        duty.paid_minutes = 60
    return snapshot


@pytest.mark.parametrize("daily_cap,accepted", [(240, False), (300, True)])
def test_autumn_dst_counts_five_elapsed_hours_in_four_wall_hours(daily_cap, accepted):
    day = date(2026, 10, 25)
    snapshot = dated_case(day, day, [(localize(day, "00:00", "Europe/Vienna"), localize(day, "04:00", "Europe/Vienna"))])
    snapshot.profiles[0].max_daily_minutes = daily_cap
    assert validate(snapshot, plan(snapshot)).valid is accepted
    result = solver.solve(snapshot, 3, partial=True)
    assert len(result.assignments) == int(accepted)
    assert result.validation.valid


def test_week_crossing_duty_is_split_at_local_monday_and_iso_year():
    # Sunday 23:00 -> Monday 03:00 local: one hour in 2025-W52,
    # three hours in 2026-W01. Wednesday adds two in that same ISO week.
    start, end = date(2025, 12, 28), date(2025, 12, 31)
    snapshot = dated_case(start, end, [
        (datetime(2025, 12, 28, 22, tzinfo=UTC), datetime(2025, 12, 29, 2, tzinfo=UTC)),
        (datetime(2025, 12, 31, 7, tzinfo=UTC), datetime(2025, 12, 31, 9, tzinfo=UTC)),
    ])
    profile = snapshot.profiles[0]
    profile.max_weekly_minutes = 4 * 60
    checked = validate(snapshot, plan(snapshot))
    assert not checked.valid
    assert any(d.code == "weekly_limit" and d.date == "2025-12-29" for d in checked.diagnostics)
    assert len(solver.solve(snapshot, 3, partial=True).assignments) == 1
    profile.max_weekly_minutes = 5 * 60
    assert validate(snapshot, plan(snapshot)).valid
    assert len(solver.solve(snapshot, 3, partial=True).assignments) == 2


def test_strictest_assigned_profile_wins_but_unassigned_limit_does_not_apply():
    snapshot = case(1, [shift("a", 5, 8, 8), shift("b", 6, 8, 8)])
    strict = snapshot.profiles[0].model_copy(update={"id": "strict", "max_weekly_minutes": 480})
    snapshot.profiles.append(strict)
    assert len(solver.solve(snapshot, 3, partial=True).assignments) == 2
    snapshot.employees[0].profile_ids.append("strict")
    assert not validate(snapshot, plan(snapshot)).valid
    result = solver.solve(snapshot, 3, partial=True)
    assert len(result.assignments) == 1
    assert result.validation.valid


def test_quality_timeout_preserves_independently_validated_partial_incumbent(monkeypatch):
    snapshot = case(1, [shift("a", 5, 8, 8), shift("b", 6, 8, 8)])
    snapshot.profiles[0].max_weekly_minutes = 480
    original = cp_model.CpSolver.solve
    calls = []

    def first_solution_then_unknown(self, model, *args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            return cp_model.UNKNOWN
        return original(self, model, *args, **kwargs)

    monkeypatch.setattr(cp_model.CpSolver, "solve", first_solution_then_unknown)
    result = solver.solve(snapshot, 3, partial=True)
    assert len(calls) == 2
    assert result.solver_status == "FEASIBLE"
    assert result.parameters["last_optimization_status"] == "UNKNOWN"
    assert len(result.assignments) == 1
    assert result.validation.valid and not result.validation.complete
    assert validate(snapshot, result.assignments).valid


def test_unknown_without_incumbent_never_returns_unchecked_assignments(monkeypatch):
    monkeypatch.setattr(cp_model.CpSolver, "solve", lambda *args, **kwargs: cp_model.UNKNOWN)
    result = solver.solve(case(1), 3, partial=True)
    assert result.solver_status == "UNKNOWN"
    assert not result.assignments and not result.validation.valid
    assert result.metrics["planning_diagnostics"]["employees"]["e0"]["reason"] == "no_valid_plan"


def test_no_rule_requires_every_eligible_employee_to_receive_a_duty():
    snapshot = case(3)
    for employee in snapshot.employees:
        employee.target_minutes = 480
    result = solver.solve(snapshot, 3, partial=True)
    assert result.validation.complete
    assert len(result.assignments) == 1  # demand.maximum=1, three eligible people
    assert sum(m["paid_minutes"] == 0 for m in result.metrics["employees"].values()) == 2
    diagnostics = result.metrics["planning_diagnostics"]
    assert diagnostics["objective_weights"] == snapshot.objectives.model_dump()
    assert sorted(d["reason"] for d in diagnostics["employees"].values()) == [
        "assigned", "not_selected_with_candidates", "not_selected_with_candidates"
    ]
    assert all(d["eligible_demands"] == 1 for d in diagnostics["employees"].values())


def test_linear_hours_target_can_tie_while_block_goal_concentrates_work():
    from sp5generator.models import Objectives

    snapshot = case(3, [shift("a", 5, 8, 8), shift("b", 6, 8, 8), shift("c", 7, 8, 8)])
    for employee in snapshot.employees:
        employee.target_minutes = 40 * 60
    snapshot.profiles[0].min_rest_minutes = 660
    snapshot.profiles[0].weekly_rest_minutes = 2160
    snapshot.objectives = Objectives(
        hours=1, changes=0, nights=0, weekends=0, holidays=0, wishes=0,
        workday_transitions=100,
    )
    distributed = [
        Assignment(employee_id=f"e{i}", demand_id=d.id)
        for i, d in enumerate(snapshot.demands)
    ]
    assert validate(snapshot, distributed).complete
    result = solver.solve(snapshot, 3, partial=True)
    assert result.solver_status == "OPTIMAL" and result.validation.complete
    assert len({a.employee_id for a in result.assignments}) == 1
    costs = result.metrics["objective_contributions"]
    # All people remain below target: total L1 shortfall is identical.
    assert costs["hours"] == 3 * (2400 - 480) == 5760
    # One three-day block has two transitions; three one-day blocks have six.
    assert costs["workday_transitions"] == 2
    assert result.objective_value == 5760 + 2 * 100
    assert sum(d["reason"] == "not_selected_with_candidates" for d in result.metrics["planning_diagnostics"]["employees"].values()) == 2


@pytest.mark.parametrize("excluded,code", [
    ("approval", "approval"), ("employment", "employment"),
    ("availability", "availability"), ("team", "team"),
])
def test_nonassignment_diagnostics_use_actual_eligibility(excluded, code):
    from sp5generator.models import Availability

    snapshot = case(1)
    employee = snapshot.employees[0]
    if excluded == "approval":
        employee.approvals.clear()
    elif excluded == "employment":
        employee.employment_start = date(2026, 1, 6)
    elif excluded == "availability":
        employee.availability = [Availability(valid_from=date(2026, 1, 5), valid_until=date(2026, 1, 11), weekdays=[6])]
    else:
        employee.team_ids.clear()
    result = solver.solve(snapshot, 3, partial=True)
    diagnostic = result.metrics["planning_diagnostics"]["employees"]["e0"]
    assert diagnostic == {
        "positive_capacity_demands": 1, "eligible_demands": 0,
        "eligible_required_demands": 0, "exclusions": {code: 1},
        "assigned_demands": 0, "reason": "individually_ineligible",
    }
    assert result.validation.valid and not result.validation.complete


@pytest.mark.parametrize("maximum,reason", [(0, "no_positive_capacity_demand"), (1, "not_selected_with_candidates")])
def test_optional_and_zero_capacity_demands_are_distinguished(maximum, reason):
    snapshot = case(1)
    snapshot.demands[0].minimum = 0
    snapshot.demands[0].maximum = maximum
    result = solver.solve(snapshot, 3, partial=True)
    diagnostic = result.metrics["planning_diagnostics"]["employees"]["e0"]
    assert diagnostic["reason"] == reason
    assert diagnostic["eligible_required_demands"] == 0
    assert diagnostic["eligible_demands"] == maximum
    assert diagnostic["exclusions"] == ({"zero_capacity": 1} if maximum == 0 else {})
    assert result.validation.complete


def test_candidate_exclusions_count_each_reason_without_claiming_disjoint_people():
    snapshot = case(1)
    snapshot.employees[0].approvals.clear()
    snapshot.employees[0].team_ids.clear()
    result = solver.solve(snapshot, 3, partial=True)
    diagnostic = result.metrics["planning_diagnostics"]["employees"]["e0"]
    assert diagnostic["positive_capacity_demands"] == 1
    assert diagnostic["exclusions"] == {"approval": 1, "team": 1}


def test_failed_input_check_does_not_publish_candidate_analysis():
    snapshot = case(1)
    snapshot.profiles[0].confirmed = False
    result = solver.solve(snapshot, 3, partial=True)
    assert result.solver_status == "MODEL_INVALID"
    assert "planning_diagnostics" not in result.metrics
