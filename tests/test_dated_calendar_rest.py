"""Dated weekly profiles: direct model coverage and timeout safety.

Only synthetic duties; 11h daily / 36h weekly, without invented hour caps.
"""
from datetime import date

import pytest
from ortools.sat.python import cp_model

from sp5generator import solver
from sp5generator.models import Assignment
from sp5generator.validator import validate
from test_core_rules import case, shift


def dated_case(profile_day=10, assigned=True, planning_day=5):
    snapshot = case(1, [shift('plan', 5, 16, 8), shift('wed', 7, 8, 8),
                        shift('fri', 9, 0, 16), shift('sun', 11, 0, 8)])
    if planning_day == 11:
        snapshot = case(1, [shift('plan', 11, 0, 8), shift('mon', 5, 16, 8),
                            shift('wed', 7, 8, 8), shift('fri', 9, 0, 16)])
    snapshot.period_start = snapshot.period_end = date(2026, 1, planning_day)
    snapshot.profiles[0].min_rest_minutes = 660
    weekly = snapshot.profiles[0].model_copy(update={
        'id': 'weekly', 'valid_from': date(2026, 1, profile_day),
        'valid_until': date(2026, 1, profile_day), 'weekly_rest_minutes': 2160,
    })
    snapshot.profiles.append(weekly)
    if assigned:
        snapshot.employees[0].profile_ids.append('weekly')
    snapshot.assignments = [Assignment(employee_id='e0', demand_id=d, fixed=True)
                            for d in (('wed', 'fri', 'sun') if planning_day == 5 else ('mon', 'wed', 'fri'))]
    return snapshot


@pytest.mark.parametrize('profile_day', [4, 5, 10, 12])
@pytest.mark.parametrize('assigned', [False, True])
@pytest.mark.parametrize('partial', [False, True])
@pytest.mark.parametrize('planning_day', [5, 11])
def test_dated_weekly_rest_is_enforced_directly_for_entire_planning_week(profile_day, assigned, partial, planning_day):
    snapshot = dated_case(profile_day, assigned, planning_day)
    applies = assigned and 5 <= profile_day <= 11
    proposed = snapshot.assignments + [Assignment(employee_id='e0', demand_id='plan')]
    # Selected: longest free interval 32h; without the planning duty: 56h.
    # Every inter-duty daily rest is >=32h, so the 11h rule is not the cause.
    checked = validate(snapshot, proposed)
    assert checked.valid is (not applies)
    assert {d.code for d in checked.diagnostics} == ({'weekly_rest'} if applies else set())
    assert validate(snapshot, snapshot.assignments).valid
    result = solver.solve(snapshot, 3, partial=partial)
    if applies and not partial:
        assert result.solver_status == 'INFEASIBLE'
        assert result.assignments == []
        return
    assert result.solver_status == 'OPTIMAL'
    assert result.validation.valid
    assert validate(snapshot, result.assignments).valid
    assert len(result.assignments) == (3 if applies else 4)
    assert result.metrics['separation_rounds'] == 0


def test_unknown_after_rejected_rolling_candidate_never_publishes_it(monkeypatch):
    # Rolling windows still use independent separation; calendar weeks now have
    # direct coverage. Exercise a real rejected candidate, not a fake validator.
    from test_spill_rest import spill_case
    snapshot = spill_case("rolling_elapsed")
    real_solve = cp_model.CpSolver.solve
    calls = []

    def interrupted(self, model, *args, **kwargs):
        calls.append(model)
        if len(calls) == 1:
            return real_solve(self, model, *args, **kwargs)
        return cp_model.UNKNOWN

    monkeypatch.setattr(cp_model.CpSolver, 'solve', interrupted)
    result = solver.solve(snapshot, 3, partial=True)
    assert len(calls) == 2
    assert result.solver_status == 'UNKNOWN'
    assert not result.validation.valid
    assert result.assignments == []
