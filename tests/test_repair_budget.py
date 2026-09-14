"""Searches exhaust their assigned budgets without spending real wall time."""

import pytest
from ortools.sat.python import cp_model

from sp5generator import solver
from sp5generator.models import Objectives
from sp5generator.validator import validate
from test_core_rules import case, shift


def full_budget_run(monkeypatch, *, time_limit=120, partial=True, repair=True):
    snapshot = case(1, [shift('a', 9, 8, 8), shift('b', 10, 8, 8)])
    snapshot.employees[0].target_minutes = 480
    snapshot.objectives = Objectives(
        hours=1, changes=0, nights=0, weekends=0, holidays=0, wishes=0,
    )
    real_search = cp_model.CpSolver.solve
    elapsed = [0.0]
    searches = []

    def search(self, model, *args, **kwargs):
        budget = self.parameters.max_time_in_seconds
        status = real_search(self, model, *args, **kwargs)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        if self.parameters.fix_variables_to_their_hinted_value:
            # Keep recursive warm-start certification real; only optimization
            # searches simulate the hard instances that exhaust their budget.
            return status
        searches.append({'started_seconds': elapsed[0], 'budget_seconds': budget})
        elapsed[0] += budget
        # A tiny model actually proves optimality. Simulate the native status
        # of a budget-exhausting search while retaining its real checked plan.
        return cp_model.FEASIBLE

    monkeypatch.setattr(solver, 'monotonic', lambda: elapsed[0])
    monkeypatch.setattr(cp_model.CpSolver, 'solve', search)
    result = solver.solve(snapshot, time_limit, partial=partial, _repair=repair)
    assert result.assignments
    assert result.validation.valid
    assert validate(snapshot, result.assignments).valid
    return result, searches


@pytest.mark.parametrize('time_limit', [120, 200])
def test_repair_starts_early_when_searches_exhaust_their_budgets(monkeypatch, time_limit):
    result, searches = full_budget_run(monkeypatch, time_limit=time_limit)
    trace = result.parameters['search_trace']
    coverage, quality = [entry for entry in trace if entry['phase'] != 'repair']
    repairs = [entry for entry in trace if entry['phase'] == 'repair']
    phase_limit = time_limit * 0.4

    assert coverage['phase'] == 'vacancies'
    assert quality['phase'] == 'quality'
    assert coverage['budget_seconds'] == pytest.approx(phase_limit * 0.8)
    assert quality['budget_seconds'] == pytest.approx(phase_limit * 0.2 - 1)
    for entry, actual_search in zip((coverage, quality), searches[:2], strict=True):
        assert entry['native_status'] == 'FEASIBLE'
        assert entry['started_seconds'] == pytest.approx(actual_search['started_seconds'])
        assert entry['budget_seconds'] == pytest.approx(actual_search['budget_seconds'])
        assert entry['search_seconds'] == pytest.approx(actual_search['budget_seconds'])
    assert coverage['search_seconds'] + quality['search_seconds'] <= phase_limit
    assert repairs
    assert repairs[0]['started_seconds'] == pytest.approx(phase_limit - 1)
    assert repairs[0]['started_seconds'] < 0.6 * time_limit
    assert result.runtime_seconds <= time_limit


@pytest.mark.parametrize(('time_limit', 'repair', 'partial'), [
    (120, False, True),
    (200, False, True),
    (119.999, True, True),
    (5, True, True),
    (120, True, False),
])
def test_disabled_repair_retains_full_search_budget(monkeypatch, time_limit, repair, partial):
    result, searches = full_budget_run(
        monkeypatch, time_limit=time_limit, repair=repair, partial=partial,
    )
    trace = result.parameters['search_trace']
    assert all(entry['phase'] != 'repair' for entry in trace)
    assert len(searches) == len(trace)
    for entry, actual_search in zip(trace, searches, strict=True):
        assert entry['budget_seconds'] == pytest.approx(actual_search['budget_seconds'])
        assert entry['search_seconds'] == pytest.approx(actual_search['budget_seconds'])
    if partial:
        coverage, quality = trace
        assert coverage['phase'] == 'vacancies'
        assert quality['phase'] == 'quality'
        assert coverage['budget_seconds'] == pytest.approx(time_limit * 0.8)
        validation_allowance = min(1.0, time_limit * 0.05)
        assert quality['budget_seconds'] == pytest.approx(time_limit * 0.2 - validation_allowance)
        assert result.runtime_seconds == pytest.approx(time_limit - validation_allowance)
    else:
        feasibility, = trace
        assert feasibility['phase'] == 'feasibility'
        assert feasibility['budget_seconds'] == pytest.approx(time_limit)
        assert result.runtime_seconds == pytest.approx(time_limit)
