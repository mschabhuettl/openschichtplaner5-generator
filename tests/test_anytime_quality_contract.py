"""Counterexamples for bounded quality search, using the production CP model.

These tests assess phase isolation; they do not enable an anytime strategy.
"""

import pytest
from ortools.sat.python import cp_model

from sp5generator import solver
from sp5generator.models import Assignment, Objectives
from sp5generator.validator import validate
from test_core_rules import case, shift


def coverage_model(monkeypatch, snapshot=None):
    if snapshot is None:
        snapshot = case(1, [shift('a', 5, 8, 8), shift('b', 6, 8, 8)])
    snapshot.employees[0].target_minutes = 480
    snapshot.objectives = Objectives(
        hours=1, changes=0, nights=0, weekends=0, holidays=0, wishes=0,
        workday_transitions=0,
    )
    captured = []

    def capture(self, model, *args, **kwargs):
        captured.append(model.clone())
        return cp_model.UNKNOWN

    with monkeypatch.context() as patch:
        patch.setattr(cp_model.CpSolver, 'solve', capture)
        result = solver.solve(snapshot, 3, partial=True)
    assert result.solver_status == 'UNKNOWN' and len(captured) == 1
    assert not captured[0].validate()
    return snapshot, captured[0]


def variables(model, prefix):
    return [model.get_int_var_from_proto_index(i)
            for i, var in enumerate(model.proto.variables) if var.name.startswith(prefix)]


def checked_search(snapshot, model):
    search = cp_model.CpSolver()
    search.parameters.num_search_workers = 1
    search.parameters.max_time_in_seconds = 3
    assert search.solve(model) == cp_model.OPTIMAL
    assignments = [Assignment(employee_id='e0', demand_id=d.id)
                   for d in snapshot.demands
                   if (choices := variables(model, 'assign:e0:' + d.id))
                   and search.value(choices[0])]
    assert validate(snapshot, assignments).valid
    return (int(search.value(sum(variables(model, 'vacancy:')))),
            sum(snapshot.shifts[i].paid_minutes for i, d in enumerate(snapshot.demands)
                if any(a.demand_id == d.id for a in assignments)))


@pytest.mark.parametrize('fix_incumbent_coverage', [False, True])
def test_quality_optimal_does_not_prove_global_coverage(monkeypatch, fix_incumbent_coverage):
    snapshot, primary = coverage_model(monkeypatch)
    quality = primary.clone()
    if fix_incumbent_coverage:
        quality.add(sum(variables(quality, 'vacancy:')) == 1)
    quality.minimize(sum(variables(quality, 'hours:')))
    # Native OPTIMAL is only relative to this objective and these constraints.
    # Unconstrained quality sacrifices coverage; fixed coverage cannot prove it.
    assert checked_search(snapshot, quality) == (1, 480)
    assert checked_search(snapshot, primary) == (0, 960)
    # Zero hours deviation is NOT preferable to full coverage in the public
    # lexicographic contract. Both plans independently satisfy all hard rules.


def test_quality_bound_must_not_leak_into_resumed_coverage(monkeypatch):
    snapshot, primary = coverage_model(monkeypatch)
    quality = primary.clone()
    quality.add(sum(variables(quality, 'hours:')) <= 0)
    quality.minimize(sum(variables(quality, 'vacancy:')))
    # Even without a fixed-vacancy equality, retaining the former quality cap
    # blocks coverage improvements that necessarily increase target deviation.
    assert checked_search(snapshot, quality) == (1, 480)
    assert checked_search(snapshot, primary) == (0, 960)


@pytest.mark.parametrize('rule', ['weekly_cap', 'daily_cap', 'rest', 'approval'])
def test_quality_clone_preserves_configured_hard_constraints(monkeypatch, rule):
    snapshot = case(1, [shift('a', 5, 8, 8), shift('b', 6, 8, 8)])
    profile = snapshot.profiles[0]
    if rule == 'weekly_cap':
        profile.max_weekly_minutes = 480
    elif rule == 'daily_cap':
        # Explicit configuration, never inferred from nominal hours.
        snapshot.shifts[1] = shift('b', 6, 8, 9)
        profile.max_daily_minutes = 480
    elif rule == 'rest':
        snapshot.shifts[1] = shift('b', 6, 2, 8)
        profile.min_rest_minutes = 660  # Ten hours between these duties.
    else:
        snapshot.employees[0].approvals[0].valid_until = snapshot.period_start

    snapshot, primary = coverage_model(monkeypatch, snapshot)
    quality = primary.clone()
    quality.add(sum(variables(quality, 'vacancy:')) == 1)
    quality.minimize(sum(variables(quality, 'hours:')))
    assert checked_search(snapshot, primary) == (1, 480)
    assert checked_search(snapshot, quality) == (1, 480)

    # Full coverage must remain impossible in both independent models.
    for model in (primary, quality):
        model.add(sum(variables(model, 'vacancy:')) == 0)
        search = cp_model.CpSolver()
        search.parameters.num_search_workers = 1
        search.parameters.max_time_in_seconds = 3
        assert search.solve(model) == cp_model.INFEASIBLE
