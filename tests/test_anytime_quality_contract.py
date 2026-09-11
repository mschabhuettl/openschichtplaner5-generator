"""Counterexamples for bounded quality search, using the production CP model.

These tests assess phase isolation and controlled real-search quality gains.
"""

import pytest
from ortools.sat.python import cp_model

from sp5generator import solver
from sp5generator.models import Assignment, Diagnostic, Objectives, Result, Validation
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


@pytest.mark.parametrize('rule', ['weekly_cap', 'daily_cap', 'rest', 'approval',
                                       'overlap', 'daily_elapsed', 'weekly_elapsed'])
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
    elif rule == 'overlap':
        snapshot.shifts[1] = shift('b', 5, 12, 8)
        profile.min_rest_minutes = 0
    elif rule in ('daily_elapsed', 'weekly_elapsed'):
        for duty in snapshot.shifts:
            duty.paid_minutes = 60
        if rule == 'daily_elapsed':
            snapshot.shifts[1] = shift('b', 5, 17, 8)
            snapshot.shifts[1].paid_minutes = 60
            profile.min_rest_minutes = 0
            profile.max_daily_minutes = 480
        else:
            profile.max_weekly_minutes = 480
    else:
        snapshot.employees[0].approvals[0].valid_until = snapshot.period_start

    snapshot, primary = coverage_model(monkeypatch, snapshot)
    quality = primary.clone()
    quality.add(sum(variables(quality, 'vacancy:')) == 1)
    quality.minimize(sum(variables(quality, 'hours:')))
    paid = 60 if rule in ('daily_elapsed', 'weekly_elapsed') else 480
    assert checked_search(snapshot, primary) == (1, paid)
    assert checked_search(snapshot, quality) == (1, paid)

    # Full coverage must remain impossible in both independent models.
    for model in (primary, quality):
        model.add(sum(variables(model, 'vacancy:')) == 0)
        search = cp_model.CpSolver()
        search.parameters.num_search_workers = 1
        search.parameters.max_time_in_seconds = 3
        assert search.solve(model) == cp_model.INFEASIBLE


def test_quality_clone_does_not_invent_a_24_hour_duty_ban(monkeypatch):
    snapshot = case(1, [shift('a', 5, 8, 24)])
    snapshot.shifts[0].paid_minutes = 480
    snapshot, primary = coverage_model(monkeypatch, snapshot)
    quality = primary.clone()
    quality.add(sum(variables(quality, 'vacancy:')) == 0)
    quality.minimize(sum(variables(quality, 'hours:')))
    # No configured daily/weekly maximum: duration alone is not a violation.
    assert checked_search(snapshot, primary) == (0, 480)
    assert checked_search(snapshot, quality) == (0, 480)


def test_conditional_quality_unknown_keeps_valid_coverage_result(monkeypatch):
    snapshot = case(1, [shift('a', 5, 8, 8), shift('b', 6, 8, 8)])
    snapshot.profiles[0].max_weekly_minutes = 480
    original = cp_model.CpSolver.solve
    budgets = []

    def coverage_then_unknown(self, model, *args, **kwargs):
        budgets.append(self.parameters.max_time_in_seconds)
        if len(budgets) == 2:
            return cp_model.UNKNOWN
        assert original(self, model, *args, **kwargs) == cp_model.OPTIMAL
        return cp_model.FEASIBLE

    monkeypatch.setattr(cp_model.CpSolver, 'solve', coverage_then_unknown)
    result = solver.solve(snapshot, 3, partial=True)
    assert len(budgets) == 2 and 0 < budgets[0] <= 2.4
    assert result.solver_status == 'FEASIBLE'
    assert result.metrics['objective_phase'] == 'vacancies'
    assert result.objective_value == 1
    assert result.parameters['last_optimization_status'] == 'UNKNOWN'
    assert not result.parameters['coverage_proven']
    assert len(result.assignments) == 1
    assert validate(snapshot, result.assignments).valid
    coverage, unknown = result.parameters['search_trace']
    assert coverage['accepted'] and coverage['independently_valid']
    assert unknown['phase'] == 'quality'
    assert unknown['native_status'] == 'UNKNOWN'
    assert not unknown['accepted'] and unknown['independently_valid'] is None
    assert 'weighted_quality_cost' not in unknown
    assert 'objective_value' not in unknown


def test_trace_does_not_count_validator_rejected_candidate_as_incumbent(monkeypatch):
    snapshot = case(1, [shift('a', 5, 8, 8)])
    original = solver.validate
    rejected = []

    def reject_once(source, assignments):
        if assignments and not rejected:
            rejected.append(True)
            # Exercise the existing exact no-good separation path.
            return Validation(valid=False, complete=False, diagnostics=[
                Diagnostic(code='night_block', message='Synthetic separation probe'),
            ])
        return original(source, assignments)

    monkeypatch.setattr(solver, 'validate', reject_once)
    result = solver.solve(snapshot, 3, partial=True)
    trace = result.parameters['search_trace']
    assert rejected and len(trace) == 3
    assert trace[0]['native_status'] == 'OPTIMAL'
    assert trace[0]['independently_valid'] is False
    assert not trace[0]['accepted']
    assert 'weighted_quality_cost' not in trace[0]
    assert all(t['accepted'] and t['independently_valid'] for t in trace[1:])
    assert result.validation.valid


def test_conditional_quality_shares_original_deadline(monkeypatch):
    snapshot = case(1, [shift('a', 5, 8, 8), shift('b', 6, 8, 8)])
    snapshot.profiles[0].max_weekly_minutes = 480
    original = cp_model.CpSolver.solve
    elapsed = [0.0]
    budgets = []
    monkeypatch.setattr(solver, 'monotonic', lambda: elapsed[0])

    def exhaust_phase(self, model, *args, **kwargs):
        budgets.append(self.parameters.max_time_in_seconds)
        status = original(self, model, *args, **kwargs)
        assert status == cp_model.OPTIMAL
        elapsed[0] += budgets[-1]
        return cp_model.FEASIBLE if len(budgets) == 1 else status

    monkeypatch.setattr(cp_model.CpSolver, 'solve', exhaust_phase)
    result = solver.solve(snapshot, 3, partial=True)
    result = Result.model_validate_json(result.model_dump_json())
    assert result.best_bound == result.objective_value
    assert result.metrics["quality_scope"] == "fixed incumbent coverage; global coverage unproven"
    assert budgets == pytest.approx([2.4, 0.45])
    assert result.runtime_seconds <= 3
    assert result.solver_status == 'FEASIBLE'
    assert result.parameters['last_optimization_status'] == 'OPTIMAL'
    assert result.metrics['objective_phase'] == 'quality'
    assert validate(snapshot, result.assignments).valid
    first, second = result.parameters['search_trace']
    assert [t['budget_seconds'] for t in (first, second)] == pytest.approx(budgets)
    assert first['started_seconds'] == 0
    assert first['search_seconds'] == pytest.approx(2.4)
    assert second['started_seconds'] == pytest.approx(2.4)
    assert second['search_seconds'] == pytest.approx(0.45)
    # Conditional native OPTIMAL stays visible without promoting overall status.
    assert second['native_status'] == 'OPTIMAL'
    assert first['vacancy_count'] == second['vacancy_count'] == 1
    assert first['weighted_quality_cost'] >= second['weighted_quality_cost']


@pytest.mark.parametrize('change_weight', [0, 100, 600])
@pytest.mark.parametrize('quality_presolve', [False, True])
@pytest.mark.parametrize('unfillable', [False, True])
def test_certified_hint_allows_real_fixed_coverage_quality_gain(
    monkeypatch, quality_presolve, unfillable, change_weight,
):
    """Move a certified hint only when the complete weighted cost improves."""
    snapshot = case(2, [shift('a', 5, 8, 8), shift('b', 6, 8, 8)])
    for employee in snapshot.employees:
        employee.target_minutes = 480
    snapshot.objectives = Objectives(
        hours=1, changes=change_weight, nights=0, weekends=0, holidays=0, wishes=0,
        workday_transitions=0,
    )
    snapshot.assignments = [Assignment(employee_id='e0', demand_id=d.id)
                            for d in snapshot.demands]
    if unfillable:
        snapshot.positions.append(snapshot.positions[0].model_copy(
            update={'id': 'unapproved', 'function_id': 'unapproved'}))
        snapshot.demands.append(snapshot.demands[0].model_copy(
            update={'id': 'unfillable', 'position_id': 'unapproved'}))
    assert validate(snapshot, snapshot.assignments).valid
    original = cp_model.CpSolver.solve
    calls = []

    def controlled_search(self, model, *args, **kwargs):
        calls.append(model.clone())
        if len(calls) == 2:
            # Accept the certified incumbent in coverage, without giving that
            # phase an opportunity to accidentally balance hours first.
            self.parameters.stop_after_first_solution = True
        elif len(calls) == 3:
            self.parameters.stop_after_first_solution = False
            self.parameters.cp_model_presolve = quality_presolve
            assert not self.parameters.fix_variables_to_their_hinted_value
            assert len(model.proto.solution_hint.vars) == len(model.proto.variables)
        return original(self, model, *args, **kwargs)

    monkeypatch.setattr(cp_model.CpSolver, 'solve', controlled_search)
    result = solver.solve(snapshot, 5, partial=True)
    assert len(calls) == 3  # certificate, coverage, conditional quality
    coverage, quality = result.parameters['search_trace']
    assert coverage['weighted_quality_cost'] == 960
    assert quality['weighted_quality_cost'] == min(960, 2 * change_weight)
    assert coverage['vacancy_count'] == quality['vacancy_count'] == int(unfillable)
    assert quality['native_status'] == 'OPTIMAL'
    assert coverage['independently_valid'] and quality['independently_valid']
    assert validate(snapshot, result.assignments).valid
    original_pairs = {(a.employee_id, a.demand_id) for a in snapshot.assignments}
    final_pairs = {(a.employee_id, a.demand_id) for a in result.assignments}
    changed = len(original_pairs ^ final_pairs)
    paid = sorted(m['paid_minutes'] for m in result.metrics['employees'].values())
    # Independent arithmetic: moving one duty removes one assignment and adds
    # another, so the configured change cost is paid twice, not once.
    hours_cost = sum(abs(minutes - 480) for minutes in paid)
    assert quality['weighted_quality_cost'] == hours_cost + changed * change_weight
    if change_weight < 480:
        assert paid == [480, 480] and changed == 2
    else:
        assert paid == [0, 960] and changed == 0
        assert final_pairs == original_pairs
        # Better target distribution alone would worsen this objective.
        assert 2 * change_weight > hours_cost
    assert all(not a.fixed for a in snapshot.assignments)
