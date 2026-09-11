"""Dated weekly profiles: characterize model separation and timeout safety.

Only synthetic duties; 11h daily / 36h weekly, without invented hour caps.
"""
from datetime import date

import pytest
from ortools.sat.python import cp_model

from sp5generator import solver
from sp5generator.models import Assignment
from sp5generator.validator import validate
from test_core_rules import case, shift


def dated_case(profile_day=10, assigned=True):
    snapshot = case(1, [shift('plan', 5, 16, 8), shift('wed', 7, 8, 8),
                        shift('fri', 9, 0, 16), shift('sun', 11, 0, 8)])
    snapshot.period_end = snapshot.period_start
    snapshot.profiles[0].min_rest_minutes = 660
    weekly = snapshot.profiles[0].model_copy(update={
        'id': 'weekly', 'valid_from': date(2026, 1, profile_day),
        'valid_until': date(2026, 1, profile_day), 'weekly_rest_minutes': 2160,
    })
    snapshot.profiles.append(weekly)
    if assigned:
        snapshot.employees[0].profile_ids.append('weekly')
    snapshot.assignments = [Assignment(employee_id='e0', demand_id=d, fixed=True)
                            for d in ('wed', 'fri', 'sun')]
    return snapshot


@pytest.mark.parametrize('profile_day', [5, 10])
@pytest.mark.parametrize('assigned', [False, True])
def test_dated_weekly_rest_requires_separation_only_outside_planning_dates(profile_day, assigned):
    snapshot = dated_case(profile_day, assigned)
    proposed = snapshot.assignments + [Assignment(employee_id='e0', demand_id='plan')]
    # Selected: longest free interval 32h; without Monday: 56h.
    # Every inter-duty daily rest is >=32h, so the 11h rule is not the cause.
    checked = validate(snapshot, proposed)
    assert checked.valid is (not assigned)
    assert {d.code for d in checked.diagnostics} == ({'weekly_rest'} if assigned else set())
    assert validate(snapshot, snapshot.assignments).valid
    result = solver.solve(snapshot, 3, partial=True)
    assert result.solver_status == 'OPTIMAL'
    assert result.validation.valid
    assert validate(snapshot, result.assignments).valid
    assert len(result.assignments) == (3 if assigned else 4)
    assert result.metrics['separation_rounds'] == int(assigned and profile_day == 10)


def test_unknown_after_rejected_calendar_candidate_never_publishes_it(monkeypatch):
    snapshot = dated_case()
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
