"""Personal work inside the planning period blocks and counts, but covers nothing.

All fixtures are synthetic. The checks assert that explicit source work with
individual times is modelled instead of dropped, and that it never becomes a
way around a staffing demand or a hard rule.
"""
from datetime import date

import pytest

from sp5generator.domain import input_diagnostics
from sp5generator.models import Assignment, BoundaryWork
from sp5generator.solver import solve
from sp5generator.timeutils import bounds
from sp5generator.validator import validate
from test_core_rules import case, shift


def personal(minutes=480, day=5, start=8, length=8):
    """One demand plus explicit personal work on the same planning day."""
    snapshot = case(1, [shift("duty", day, start, length)])
    snapshot.period_start = snapshot.period_end = date(2026, 1, day)
    snapshot.profiles[0].min_rest_minutes = 660
    duty = snapshot.shifts[0]
    snapshot.boundary_work.append(BoundaryWork(
        id="personal", employee_id="e0", segments=duty.segments, kind="day",
        in_period=True, paid_minutes=minutes, source="sp5:existing",
    ))
    return snapshot


def test_in_period_personal_work_is_accepted_as_input():
    snapshot = personal()

    codes = {d.code for d in input_diagnostics(snapshot)}

    assert "boundary_period" not in codes
    assert not codes


def test_context_outside_the_period_still_may_not_start_inside():
    snapshot = personal()
    snapshot.boundary_work[0].in_period = False

    assert "boundary_period" in {d.code for d in input_diagnostics(snapshot)}


@pytest.mark.parametrize("partial", [False, True])
def test_personal_work_blocks_a_conflicting_assignment(partial):
    snapshot = personal()
    demand, = snapshot.demands

    assert not validate(snapshot, [Assignment(employee_id="e0", demand_id=demand.id)]).valid
    result = solve(snapshot, 5, partial=partial)
    assert not result.assignments
    assert result.vacancies == {demand.id: 1}
    if partial:
        assert result.solver_status in ("OPTIMAL", "FEASIBLE")


def test_personal_work_never_covers_the_demand():
    snapshot = personal()
    demand, = snapshot.demands

    report = validate(snapshot, [])

    assert "vacancy" in {d.code for d in report.diagnostics}
    assert report.valid and not report.complete
    assert demand.minimum == 1


@pytest.mark.parametrize("minutes,expected", [(0, 480), (480, 0), (960, 480)])
def test_stated_paid_minutes_count_towards_the_period_target(minutes, expected):
    """The person really works these hours; the deviation must reflect them."""
    snapshot = personal(minutes=minutes)
    snapshot.employees[0].target_minutes = 480
    snapshot.demands.clear()

    report = validate(snapshot, [])
    deviation = solve(snapshot, 5).metrics["employees"]["e0"]

    assert report.valid
    assert deviation["paid_minutes"] == minutes
    assert abs(deviation["deviation_minutes"]) == expected


def test_rest_after_personal_work_is_enforced():
    """A duty on the next morning breaches the 11 hours from personal work."""
    snapshot = case(1, [shift("next", 6, 6, 8)])
    snapshot.period_start = snapshot.period_end = date(2026, 1, 6)
    snapshot.profiles[0].min_rest_minutes = 660
    evening = shift("evening", 5, 20, 4)
    snapshot.boundary_work.append(BoundaryWork(
        id="personal", employee_id="e0", segments=evening.segments, kind="day",
        in_period=False, paid_minutes=0, source="sp5:existing",
    ))
    demand, = snapshot.demands
    blocked = validate(snapshot, [Assignment(employee_id="e0", demand_id=demand.id)])

    assert "rest" in {d.code for d in blocked.diagnostics}
    assert bounds(snapshot.boundary_work[0])[1] < bounds(snapshot.shifts[0])[0]
