"""Contradictory source duties stay visible without blocking every plan.

All fixtures are synthetic. The checks assert that a contradiction the plan
cannot undo is reported instead of making the model unsolvable, and that the
hard rules between context and new work are unchanged.
"""
from datetime import timedelta

import pytest

from sp5generator.models import Assignment, BoundaryWork
from sp5generator.solver import solve
from sp5generator.validator import validate
from test_boundary_time_contract import boundary_case
from test_boundary_work import convert


def contradicting(rule):
    """Turn the new duty into a second immutable context duty before the period."""
    snapshot = convert(boundary_case(rule))
    demand, = snapshot.demands
    shift, = [s for s in snapshot.shifts if s.id == demand.shift_id]
    snapshot.boundary_work.append(BoundaryWork(
        id=shift.id, employee_id="e0", segments=shift.segments, kind=shift.kind,
    ))
    snapshot.shifts = [s for s in snapshot.shifts if s.id != shift.id]
    snapshot.demands = []
    # Both duties are past facts; plan a later day so neither starts in period.
    snapshot.period_start = snapshot.period_end = snapshot.period_end + timedelta(days=5)
    return snapshot


@pytest.mark.parametrize("rule", ["rest", "overlap", "interleaving"])
@pytest.mark.parametrize("partial", [False, True])
def test_contradicting_source_duties_do_not_block_planning(rule, partial):
    snapshot = contradicting(rule)

    result = solve(snapshot, 5, partial=partial)

    assert result.solver_status in ("OPTIMAL", "FEASIBLE")
    assert result.validation.valid
    codes = {d.code for d in result.validation.diagnostics}
    assert "context" in codes
    assert not codes & {"rest", "overlap", "interleaving"}


@pytest.mark.parametrize("rule", ["rest", "overlap", "interleaving"])
def test_contradiction_names_both_duties(rule):
    snapshot = contradicting(rule)

    report = validate(snapshot, [])

    assert report.valid
    found = [d for d in report.diagnostics if d.code == "context" and "unvereinbar" in d.message]
    assert len(found) == 1
    assert found[0].employee_id == "e0"
    assert rule in found[0].message
    assert found[0].message.count("/") == 1


@pytest.mark.parametrize("rule", ["rest", "overlap", "interleaving"])
@pytest.mark.parametrize("partial", [False, True])
def test_new_work_against_context_stays_hard(rule, partial):
    """The relaxation is limited to fact-against-fact; planning is unchanged."""
    snapshot = convert(boundary_case(rule))
    demand, = snapshot.demands

    assert not validate(snapshot, [Assignment(employee_id="e0", demand_id=demand.id)]).valid
    result = solve(snapshot, 5, partial=partial)
    assert not result.assignments
    assert result.vacancies == {demand.id: 1}
