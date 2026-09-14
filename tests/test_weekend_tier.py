"""Synthetic assignment-level contracts for coverage, coupling and quality."""

from collections import Counter

import pytest

from sp5generator.models import Assignment, Objectives, Restriction, Snapshot
from sp5generator.solver import solve
from sp5generator.validator import validate
from test_core_rules import case, shift


def weekend_case(n=2):
    snapshot = case(n, [shift("sat", 10, 8, 8), shift("sun", 11, 8, 8)])
    snapshot.objectives = Objectives(
        hours=1, changes=0, nights=0, weekends=0, holidays=0, wishes=0,
        split_weekends=1,
    )
    for employee in snapshot.employees:
        employee.target_minutes = 480
    return snapshot


def assignment_pairs(assignments):
    return {(assignment.employee_id, assignment.demand_id) for assignment in assignments}


def split_count(assignments):
    """All counted duties in these examples start on the same weekend."""
    worked = {}
    for assignment in assignments:
        worked.setdefault(assignment.employee_id, set()).add(assignment.demand_id)
    return sum(len(days) == 1 for days in worked.values())


def assert_complete(snapshot, result):
    assert result.validation.valid and result.validation.complete
    assert validate(snapshot, result.assignments).complete
    assert not result.vacancies
    assert result.metrics["vacancy_count"] == 0


def assert_coupling_report(result, expected):
    assert result.metrics["objective_contributions"]["split_weekends"] == expected
    assert result.parameters["split_weekend_count"] == expected
    assert result.parameters["split_weekends_proven"] is True
    trace = result.parameters["search_trace"]
    couple, = [entry for entry in trace if entry["phase"] == "couple"]
    assert couple["accepted"] and couple["independently_valid"]
    assert couple["native_status"] == "OPTIMAL"
    assert couple["split_weekend_count"] == expected
    assert trace[-1]["phase"] == "quality"


@pytest.mark.parametrize("partial", [False, True])
def test_disabled_coupling_preserves_previous_result_without_extra_phase(partial):
    snapshot = weekend_case()
    snapshot.assignments = [
        Assignment(employee_id="e0", demand_id="sat"),
        Assignment(employee_id="e1", demand_id="sun"),
    ]
    snapshot.objectives = Objectives(
        hours=0, changes=1, nights=0, weekends=0, holidays=0, wishes=0,
        split_weekends=0,
    )
    legacy_data = snapshot.model_dump(mode="json")
    legacy_data["objectives"].pop("split_weekends")
    legacy = Snapshot.model_validate(legacy_data)

    previous = solve(legacy, time_limit=5, partial=partial)
    explicit_zero = solve(snapshot, time_limit=5, partial=partial)

    expected = {("e0", "sat"), ("e1", "sun")}
    for source, result in ((legacy, previous), (snapshot, explicit_zero)):
        assert_complete(source, result)
        assert result.solver_status == "OPTIMAL"
        assert assignment_pairs(result.assignments) == expected
        assert split_count(result.assignments) == 2
        assert result.metrics["objective_contributions"].get("split_weekends", 0) == 0
        assert [entry["phase"] for entry in result.parameters["search_trace"]] == [
            "vacancies" if partial else "feasibility", "quality",
        ]
    assert explicit_zero.metrics["employees"] == previous.metrics["employees"]
    assert explicit_zero.vacancies == previous.vacancies


@pytest.mark.parametrize("mode", ["full", "partial", "partial_warm", "full_warm"])
def test_coupling_wins_even_when_split_weekend_fulfils_soft_hour_targets(mode):
    # Forty employees enable the production greedy warm start in full mode.
    snapshot = weekend_case(n=40 if mode == "full_warm" else 2)
    split_plan = [
        Assignment(employee_id="e0", demand_id="sat"),
        Assignment(employee_id="e1", demand_id="sun"),
    ]
    assert validate(snapshot, split_plan).complete
    if mode == "partial_warm":
        snapshot.assignments = split_plan

    # The disabled control meets both workers' targets exactly by splitting.
    control = snapshot.model_copy(deep=True)
    control.objectives.split_weekends = 0
    previous = solve(control, time_limit=5, partial=mode.startswith("partial"))
    result = solve(snapshot, time_limit=5, partial=mode.startswith("partial"))

    assert_complete(control, previous)
    assert_complete(snapshot, result)
    assert split_count(previous.assignments) == 2
    assert sorted(employee["paid_minutes"] for employee in previous.metrics["employees"].values()) == (
        [0] * (len(snapshot.employees) - 2) + [480, 480]
    )
    assert {assignment.demand_id for assignment in result.assignments} == {"sat", "sun"}
    assert len({assignment.employee_id for assignment in result.assignments}) == 1
    assert split_count(result.assignments) == 0
    assert sorted(employee["paid_minutes"] for employee in result.metrics["employees"].values()) == (
        [0] * (len(snapshot.employees) - 1) + [960]
    )
    assert result.solver_status == "OPTIMAL"
    assert_coupling_report(result, 0)
    phases = [entry["phase"] for entry in result.parameters["search_trace"]]
    prefix = [] if mode == "full_warm" else [
        "vacancies" if mode.startswith("partial") else "feasibility",
    ]
    assert phases == prefix + ["couple", "quality"]
    if mode.endswith("warm"):
        assert result.parameters["warm_start_certificate_status"] == "OPTIMAL"


@pytest.mark.parametrize("partial", [False, True])
def test_unequal_weekend_demand_keeps_only_unavoidable_split_and_fills_every_slot(partial):
    snapshot = weekend_case()
    snapshot.demands[0].minimum = snapshot.demands[0].maximum = 2

    result = solve(snapshot, time_limit=5, partial=partial)

    assert_complete(snapshot, result)
    assert Counter(assignment.demand_id for assignment in result.assignments) == {"sat": 2, "sun": 1}
    assert len({assignment.employee_id for assignment in result.assignments}) == 2
    assert split_count(result.assignments) == 1
    assert_coupling_report(result, 1)


@pytest.mark.parametrize("partial", [False, True])
def test_coverage_precedes_coupling_when_hours_cap_requires_split_weekends(partial):
    snapshot = weekend_case()
    # Both employees can work either day, so both coupling terms exist. The
    # hard weekly cap prevents either from covering Saturday AND Sunday.
    snapshot.profiles[0].max_weekly_minutes = 480

    result = solve(snapshot, time_limit=5, partial=partial)

    assert_complete(snapshot, result)
    assert Counter(assignment.demand_id for assignment in result.assignments) == {"sat": 1, "sun": 1}
    assert len({assignment.employee_id for assignment in result.assignments}) == 2
    assert split_count(result.assignments) == 2
    assert [employee["paid_minutes"] for employee in result.metrics["employees"].values()] == [480, 480]
    assert_coupling_report(result, 2)


@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("missing_terms", ["single_day", "separate_eligibility"])
def test_enabled_objective_without_coupling_terms_keeps_original_phase_order(partial, missing_terms):
    snapshot = weekend_case()
    if missing_terms == "single_day":
        snapshot.shifts = snapshot.shifts[:1]
        snapshot.demands = snapshot.demands[:1]
    else:
        snapshot.restrictions = [
            Restriction(employee_id="e0", shift_id="sun", level=2),
            Restriction(employee_id="e1", shift_id="sat", level=2),
        ]

    result = solve(snapshot, time_limit=5, partial=partial)

    assert_complete(snapshot, result)
    assert len(result.assignments) == len(snapshot.demands)
    assert result.metrics["objective_contributions"].get("split_weekends", 0) == 0
    assert [entry["phase"] for entry in result.parameters["search_trace"]] == [
        "vacancies" if partial else "feasibility", "quality",
    ]
