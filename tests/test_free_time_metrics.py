"""Aggregate free-time reporting uses synthetic plans and occupied calendar days."""
from datetime import date

import pytest

from sp5generator.models import Assignment, BoundaryWork
from sp5generator.solver import solve
from test_core_rules import assignment, case, shift


ZERO_FREE_TIME = {
    "blocks": 0,
    "single_days": 0,
    "three_or_more": 0,
    "mean_length": 0.0,
    "longest": 0,
    "free_weekends": 0,
    "people": 0,
}


def test_free_time_aggregates_known_structure_without_personal_details():
    working_days = {"e0": (5, 7, 11, 16), "e1": (8, 9, 15, 16)}
    snapshot = case(n=4, shifts=[
        shift(f"{employee}-{day}", day, 8, 8)
        for employee, days in working_days.items() for day in days
    ])
    snapshot.period_end = date(2026, 1, 18)
    snapshot.assignments = [
        Assignment(employee_id=employee, demand_id=f"{employee}-{day}", fixed=True)
        for employee, days in working_days.items() for day in days
    ]
    snapshot.boundary_work = [BoundaryWork(
        id="context-only", employee_id="e2", kind="day",
        segments=shift("context-only", 3, 8, 8).segments,
    )]

    result = solve(snapshot, time_limit=5)

    assert result.validation.valid and result.validation.complete
    assert {(a.employee_id, a.demand_id) for a in result.assignments} == {
        (a.employee_id, a.demand_id) for a in snapshot.assignments
    }
    # e0: lengths 1, 3, 4, 2; e1: lengths 3, 5, 2. Context-only and idle
    # people contribute nothing. The mean is 20 / 7, across all blocks.
    assert result.metrics["free_time"] == {
        "blocks": 7,
        "single_days": 1,
        "three_or_more": 4,
        "mean_length": 2.86,
        "longest": 5,
        "free_weekends": 3,
        "people": 2,
    }
    for name, value in result.metrics["free_time"].items():
        assert type(value) is (float if name == "mean_length" else int)


@pytest.mark.parametrize("warm", [False, True])
def test_free_time_counts_entire_blocks_at_both_period_edges(monkeypatch, warm):
    snapshot = case(n=1, shifts=[shift("middle", 8, 8, 8)])
    if warm:
        from ortools.sat.python import cp_model

        snapshot.assignments = [assignment(d="middle")]
        original = cp_model.CpSolver.solve

        def stop_after_certificate(self, model, *args, **kwargs):
            if self.parameters.fix_variables_to_their_hinted_value:
                return original(self, model, *args, **kwargs)
            return cp_model.UNKNOWN

        monkeypatch.setattr(cp_model.CpSolver, "solve", stop_after_certificate)

    result = solve(snapshot, time_limit=5, partial=warm)

    assert result.solver_status == ("FEASIBLE" if warm else "OPTIMAL")
    assert result.validation.valid and result.validation.complete
    assert result.metrics["free_time"] == {
        "blocks": 2,
        "single_days": 0,
        "three_or_more": 2,
        "mean_length": 3.0,
        "longest": 3,
        "free_weekends": 1,
        "people": 1,
    }


@pytest.mark.parametrize("timed", [False, True])
def test_personal_work_inside_period_shortens_free_time(timed):
    snapshot = case(n=1, shifts=[shift("middle", 8, 8, 8)])
    snapshot.boundary_work = [
        BoundaryWork(
            id=f"personal-{day}", employee_id="e0", kind="day", in_period=True,
            day=None if timed else date(2026, 1, day),
            segments=shift(f"personal-{day}", day, 8, 8).segments if timed else [],
        )
        for day in (7, 10)
    ]

    result = solve(snapshot, time_limit=5)

    assert result.validation.valid and result.validation.complete
    assert result.metrics["free_time"] == {
        "blocks": 3,
        "single_days": 2,
        "three_or_more": 0,
        "mean_length": 1.33,
        "longest": 2,
        "free_weekends": 0,
        "people": 1,
    }


@pytest.mark.parametrize("timed", [False, True])
def test_personal_work_counts_without_assignments(timed):
    snapshot = case(n=1)
    snapshot.demands.clear()
    snapshot.boundary_work = [BoundaryWork(
        id="personal", employee_id="e0", kind="day", in_period=True,
        day=None if timed else date(2026, 1, 8),
        segments=shift("personal", 8, 8, 8).segments if timed else [],
    )]

    result = solve(snapshot, time_limit=5)

    assert result.validation.valid and result.validation.complete
    assert result.assignments == []
    assert result.metrics["free_time"] == {
        "blocks": 2,
        "single_days": 0,
        "three_or_more": 2,
        "mean_length": 3.0,
        "longest": 3,
        "free_weekends": 1,
        "people": 1,
    }


@pytest.mark.parametrize("mode", ["infeasible", "partial", "empty", "timeout", "invalid"])
def test_result_without_assignments_has_zero_free_time(mode):
    snapshot = case(n=1)
    if mode in ("infeasible", "partial"):
        snapshot.employees[0].approvals.clear()
    elif mode == "empty":
        snapshot.demands.clear()
    elif mode == "invalid":
        snapshot.profiles[0].confirmed = False

    result = solve(snapshot, time_limit=0 if mode == "timeout" else 5, partial=mode == "partial")

    assert result.assignments == []
    assert result.solver_status == {
        "infeasible": "INFEASIBLE", "partial": "OPTIMAL", "empty": "OPTIMAL",
        "timeout": "UNKNOWN", "invalid": "MODEL_INVALID",
    }[mode]
    assert result.metrics["free_time"] == ZERO_FREE_TIME
    assert type(result.metrics["free_time"]["mean_length"]) is float


def test_result_without_people_has_zero_free_time():
    snapshot = case(n=0)
    snapshot.demands.clear()

    result = solve(snapshot, time_limit=5)

    assert result.validation.valid and result.validation.complete
    assert result.assignments == []
    assert result.metrics["free_time"] == ZERO_FREE_TIME


@pytest.mark.parametrize("weekend_day", [10, 11])
def test_weekend_is_not_free_if_either_day_is_worked(weekend_day):
    snapshot = case(n=1, shifts=[shift("weekend", weekend_day, 8, 8)])

    result = solve(snapshot, time_limit=5)

    assert result.validation.valid and result.validation.complete
    assert result.metrics["free_time"]["free_weekends"] == 0


def test_weekend_with_sunday_outside_period_is_not_counted():
    snapshot = case(n=1)
    snapshot.period_end = date(2026, 1, 10)

    result = solve(snapshot, time_limit=5)

    assert result.validation.valid and result.validation.complete
    assert result.metrics["free_time"] == {
        "blocks": 1,
        "single_days": 0,
        "three_or_more": 1,
        "mean_length": 5.0,
        "longest": 5,
        "free_weekends": 0,
        "people": 1,
    }


def test_partial_plan_reports_free_time_of_actual_assignments():
    snapshot = case(n=1, shifts=[shift("first", 8, 8, 8), shift("second", 8, 8, 8)])

    result = solve(snapshot, time_limit=5, partial=True)

    assert result.validation.valid and not result.validation.complete
    assert len(result.assignments) == 1
    assert sum(result.vacancies.values()) == 1
    assert result.metrics["free_time"] == {
        "blocks": 2,
        "single_days": 0,
        "three_or_more": 2,
        "mean_length": 3.0,
        "longest": 3,
        "free_weekends": 1,
        "people": 1,
    }


@pytest.mark.parametrize(("source", "expected"), [
    ("night", {
        "blocks": 1, "single_days": 0, "three_or_more": 1, "mean_length": 5.0,
        "longest": 5, "free_weekends": 1, "people": 1,
    }),
    ("split", {
        "blocks": 2, "single_days": 1, "three_or_more": 1, "mean_length": 2.5,
        "longest": 4, "free_weekends": 1, "people": 1,
    }),
    ("midnight", {
        "blocks": 1, "single_days": 0, "three_or_more": 1, "mean_length": 6.0,
        "longest": 6, "free_weekends": 1, "people": 1,
    }),
    ("boundary_spill", {
        "blocks": 1, "single_days": 0, "three_or_more": 1, "mean_length": 6.0,
        "longest": 6, "free_weekends": 1, "people": 1,
    }),
])
def test_free_time_uses_actual_occupied_calendar_days(source, expected):
    snapshot = case(n=1, shifts=[shift("s", 5, 20, 2)])
    if source == "night":
        snapshot.shifts[0] = shift("s", 5, 22, 8, "night")
    elif source == "split":
        snapshot.shifts[0].segments += shift("later", 7, 20, 2).segments
    elif source == "midnight":
        snapshot.shifts[0] = shift("s", 5, 20, 4)
    else:
        snapshot.demands.clear()
        snapshot.boundary_work = [BoundaryWork(
            id="before", employee_id="e0", kind="night",
            segments=shift("before", 4, 22, 8, "night").segments,
        )]

    result = solve(snapshot, time_limit=5)

    assert result.validation.valid and result.validation.complete
    assert result.metrics["free_time"] == expected


def test_person_with_work_every_day_has_no_free_blocks():
    snapshot = case(n=1, shifts=[shift(f"d{day}", day, 8, 8) for day in range(5, 12)])

    result = solve(snapshot, time_limit=5)

    assert result.validation.valid and result.validation.complete
    assert result.metrics["free_time"] == {**ZERO_FREE_TIME, "people": 1}
