"""Deterministic repair rounds around real, independently checked CP solutions."""

from datetime import date

import pytest
from ortools.sat.python import cp_model

from sp5generator import solver
from sp5generator.domain import snapshot_hash
from sp5generator.models import Assignment, Diagnostic, Objectives, Validation
from sp5generator.validator import validate
from test_core_rules import case, shift


def repair_case():
    snapshot = case(1, [shift('a', 9, 8, 8), shift('b', 10, 8, 8)])
    snapshot.employees[0].target_minutes = 480
    snapshot.objectives = Objectives(
        hours=1, changes=0, nights=0, weekends=0, holidays=0, wishes=0,
    )
    return snapshot


def controlled_run(
    monkeypatch, snapshot, *, time_limit=120, partial=True, repair=True,
    missing_demand=None, outer_search_seconds=20, reject_full_round=False,
    round_assignments=None, outer_quality_unknown=False,
    outer_final_validation_seconds=0, round_result_transform=None,
):
    """Account for search time without waiting; solve every model with CP-SAT.

    The optional first-search restriction creates a certified, suboptimal
    incumbent without changing the production model or its quality clone.
    Recursive calls retain the real model builder, search and validator.
    """
    real_solve = solver.solve
    real_search = cp_model.CpSolver.solve
    real_validate = solver.validate
    elapsed = [0.0]
    state = {'inside_round': False, 'outer_searches': 0}
    rounds = []
    rejected_plans = []

    def search(self, model, *args, **kwargs):
        certificate = self.parameters.fix_variables_to_their_hinted_value
        outer_search = not state['inside_round'] and not certificate
        if outer_search:
            state['outer_searches'] += 1
            if outer_quality_unknown and state['outer_searches'] == 2:
                elapsed[0] += outer_search_seconds
                return cp_model.UNKNOWN
        restricted = outer_search and state['outer_searches'] == 1 and missing_demand
        if restricted:
            model = model.clone()
            restricted_variables = [
                model.get_int_var_from_proto_index(index)
                for index, variable in enumerate(model.proto.variables)
                if variable.name.startswith('assign:')
                and variable.name.endswith(':' + missing_demand)
            ]
            assert restricted_variables
            for variable in restricted_variables:
                model.add(variable == 0)
        if state['inside_round'] and round_assignments is not None:
            # Produce a deliberately worse, but still real and checked, round
            # candidate to exercise the outer acceptance rule.
            model = model.clone()
            selected_names = {'assign:' + employee + ':' + demand
                              for employee, demand in round_assignments}
            for index, variable in enumerate(model.proto.variables):
                if variable.name.startswith('assign:'):
                    model.add(model.get_int_var_from_proto_index(index)
                              == int(variable.name in selected_names))
        status = real_search(self, model, *args, **kwargs)
        if outer_search:
            assert status == cp_model.OPTIMAL
            elapsed[0] += outer_search_seconds
        return cp_model.FEASIBLE if restricted else status

    def recursive_solve(candidate, time_limit=30, partial=False, _repair=True, workers=None):
        assert partial and not _repair
        assert not state['inside_round'], 'repair rounds must not recurse again'
        # Check the actual argument before our own observation copy; copying
        # here must not conceal shallow copies in the production repair code.
        assert candidate is not snapshot
        for field in ('employees', 'profiles', 'demands', 'shifts', 'positions',
                      'restrictions', 'wishes', 'boundary_work'):
            source_items, copied_items = getattr(snapshot, field), getattr(candidate, field)
            assert copied_items is not source_items
            assert all(copied is not source
                       for source, copied in zip(source_items, copied_items, strict=True))
        source_duties = {duty.id: duty for duty in snapshot.shifts}
        source_demands = {demand.id: demand for demand in snapshot.demands}
        source_assignments = {(assignment.employee_id, assignment.demand_id): assignment
                              for assignment in snapshot.assignments}
        for duty in candidate.shifts:
            original_segments = source_duties[duty.id].segments
            assert duty.segments is not original_segments
            assert all(copied is not source for source, copied
                       in zip(original_segments, duty.segments, strict=True))
        for assignment in candidate.assignments:
            duty = source_duties[source_demands[assignment.demand_id].shift_id]
            assert assignment.segments is not duty.segments
            assert all(copied is not source for source, copied
                       in zip(duty.segments, assignment.segments, strict=True))
            original = source_assignments.get((assignment.employee_id, assignment.demand_id))
            if original is not None:
                assert assignment is not original
                assert assignment.segments is not original.segments
                assert all(copied is not source for copied in assignment.segments
                           for source in original.segments)
        rounds.append({
            'snapshot': candidate.model_copy(deep=True),
            'time_limit': time_limit,
        })
        state['inside_round'] = True
        try:
            result = real_solve(candidate, time_limit, partial=partial, _repair=_repair)
        finally:
            state['inside_round'] = False
        # Charge the reserved round budget to the outer deadline, including
        # the recursive model build and independent validation.
        elapsed[0] += time_limit
        if round_result_transform is not None:
            result = round_result_transform(result)
        return result

    def check(source, assignments):
        if state['inside_round'] and len(assignments) == 2 and reject_full_round:
            rejected_plans.append([a.model_copy(deep=True) for a in assignments])
            return Validation(valid=False, complete=False, diagnostics=[
                Diagnostic(code='night_block', message='Synthetic separation probe'),
            ])
        checked = real_validate(source, assignments)
        if not state['inside_round'] and state['outer_searches'] == 2:
            elapsed[0] += outer_final_validation_seconds
        return checked

    with monkeypatch.context() as patch:
        patch.setattr(solver, 'monotonic', lambda: elapsed[0])
        patch.setattr(cp_model.CpSolver, 'solve', search)
        patch.setattr(solver, 'solve', recursive_solve)
        patch.setattr(solver, 'validate', check)
        result = real_solve(snapshot, time_limit, partial=partial, _repair=repair)
    return result, rounds, rejected_plans


def repair_trace(result):
    return [entry for entry in result.parameters['search_trace']
            if entry['phase'] == 'repair']


@pytest.mark.parametrize('time_limit', [5, 119.999])
def test_small_time_limit_never_starts_repair(monkeypatch, time_limit):
    snapshot = repair_case()
    options = {'time_limit': time_limit, 'outer_search_seconds': 0}
    baseline, _, _ = controlled_run(monkeypatch, snapshot, repair=False, **options)
    result, rounds, _ = controlled_run(monkeypatch, snapshot, **options)
    assert not rounds
    assert not repair_trace(result)
    assert result.model_dump() == baseline.model_dump()


def test_non_partial_search_never_starts_repair(monkeypatch):
    snapshot = repair_case()
    baseline, _, _ = controlled_run(monkeypatch, snapshot, partial=False, repair=False)
    result, rounds, _ = controlled_run(monkeypatch, snapshot, partial=False)
    assert not rounds
    assert not repair_trace(result)
    assert result.model_dump() == baseline.model_dump()


@pytest.mark.parametrize('remaining_seconds', [15, 1])
def test_insufficient_remaining_budget_keeps_result_identical(monkeypatch, remaining_seconds):
    snapshot = repair_case()
    # Two 20-second searches fit within the 48-second search allowance.
    # Final validation consumes the rest except 15 or 1 seconds; neither
    # leaves enough time to start a round with its minimum 15-second budget.
    options = {'outer_final_validation_seconds': 120 - 2 * 20 - remaining_seconds}
    baseline, _, _ = controlled_run(monkeypatch, snapshot, repair=False, **options)
    result, rounds, _ = controlled_run(monkeypatch, snapshot, **options)
    assert not rounds
    assert not repair_trace(result)
    assert result.runtime_seconds == baseline.runtime_seconds == 120 - remaining_seconds
    # Reserving 60% for repair necessarily changes the advertised search
    # budgets. Check them explicitly, then compare every other result field.
    baseline_dump, result_dump = baseline.model_dump(), result.model_dump()
    for dump, phase_limit in ((baseline_dump, 120), (result_dump, 120 * 0.4)):
        coverage, quality = dump['parameters']['search_trace']
        assert coverage.pop('budget_seconds') == pytest.approx(phase_limit * 0.8)
        assert quality.pop('budget_seconds') == pytest.approx(phase_limit - 20 - 1)
    assert result_dump == baseline_dump


@pytest.mark.parametrize('change_weight', [0, 1000])
def test_repair_closes_avoidable_vacancy_with_real_model(monkeypatch, change_weight):
    snapshot = repair_case()
    snapshot.objectives.changes = change_weight
    # This demand has no approved employee and must remain vacant even after
    # the repair closes the deliberately omitted, otherwise feasible duty b.
    snapshot.positions.append(snapshot.positions[0].model_copy(
        update={'id': 'unapproved', 'function_id': 'unapproved'},
    ))
    snapshot.demands.append(snapshot.demands[0].model_copy(
        update={'id': 'unfillable', 'position_id': 'unapproved'},
    ))
    original = snapshot.model_dump_json()
    options = {'missing_demand': 'b', 'outer_search_seconds': 20}
    baseline, _, _ = controlled_run(monkeypatch, snapshot, repair=False, **options)
    result, rounds, _ = controlled_run(monkeypatch, snapshot, **options)
    assert baseline.metrics['vacancy_count'] == sum(baseline.vacancies.values()) == 2
    assert result.metrics['vacancy_count'] == sum(result.vacancies.values()) == 1
    assert result.metrics['vacancy_count'] < baseline.metrics['vacancy_count']
    assert result.vacancies == {'unfillable': 1}
    assert len(result.assignments) == 2
    assert baseline.validation.valid and not baseline.validation.complete
    assert result.validation.valid and not result.validation.complete
    checked = validate(snapshot, result.assignments)
    assert checked.valid and not checked.complete
    # Coverage takes priority even when adding a duty increases weighted cost.
    assert sum(result.metrics['weighted_objective_contributions'].values()) > sum(
        baseline.metrics['weighted_objective_contributions'].values()
    )
    assert result.metrics['objective_phase'] == 'repair'
    traces = repair_trace(result)
    trace = traces[0]
    assert trace['accepted'] is True
    assert trace['neighborhood'] == 'weekend'
    assert len(rounds) == len(traces) == 5
    assert not any(entry['accepted'] for entry in traces[1:])
    assert all(round_call['time_limit'] == 15.0 for round_call in rounds)
    assert result.runtime_seconds <= 120
    assert result.snapshot_hash == snapshot_hash(snapshot)
    assert not any(assignment.fixed for assignment in result.assignments)
    assert snapshot.model_dump_json() == original
    if change_weight:
        assert result.metrics['objective_contributions']['changes'] == 2
        assert result.metrics['weighted_objective_contributions']['changes'] == 2 * change_weight


def test_unhelpful_round_keeps_the_returned_plan(monkeypatch):
    snapshot = repair_case()
    baseline, _, _ = controlled_run(monkeypatch, snapshot, repair=False)
    result, rounds, _ = controlled_run(monkeypatch, snapshot)
    traces = repair_trace(result)
    assert len(rounds) == len(traces) == 5
    assert all(trace['accepted'] is False for trace in traces)
    assert result.assignments == baseline.assignments
    assert result.vacancies == baseline.vacancies
    assert result.validation == baseline.validation
    assert result.metrics == baseline.metrics
    assert result.metrics['objective_phase'] == 'quality'
    assert result.objective_value == baseline.objective_value
    assert result.best_bound == baseline.best_bound


def test_repair_improves_weighted_quality_at_equal_coverage(monkeypatch):
    snapshot = case(2, [shift('a', 9, 8, 8), shift('b', 10, 8, 8)])
    for employee in snapshot.employees:
        employee.target_minutes = 480
    snapshot.objectives = Objectives(
        hours=1, changes=0, nights=0, weekends=0, holidays=0, wishes=0,
    )
    snapshot.assignments = [Assignment(employee_id='e0', demand_id=demand.id)
                            for demand in snapshot.demands]
    # The original quality phase returns no incumbent; its independently
    # certified full-coverage hint remains available for a real repair solve.
    baseline, _, _ = controlled_run(
        monkeypatch, snapshot, repair=False, outer_quality_unknown=True,
    )
    result, rounds, _ = controlled_run(monkeypatch, snapshot, outer_quality_unknown=True)
    assert baseline.metrics['vacancy_count'] == result.metrics['vacancy_count'] == 0
    assert sum(baseline.metrics['weighted_objective_contributions'].values()) == 960
    assert sum(result.metrics['weighted_objective_contributions'].values()) == 0
    assert sorted(employee['paid_minutes'] for employee in result.metrics['employees'].values()) == [
        480, 480,
    ]
    traces = repair_trace(result)
    assert len(rounds) == len(traces) == 5
    assert traces[0]['accepted'] is True
    assert all(trace['accepted'] is False for trace in traces[1:])
    assert [entry['phase'] for entry in baseline.parameters['search_trace']] == [
        'vacancies', 'quality',
    ]
    assert baseline.parameters['search_trace'][1]['native_status'] == 'UNKNOWN'
    assert result.parameters['search_trace'][1]['native_status'] == 'UNKNOWN'
    assert result.metrics['objective_phase'] == 'repair'
    assert result.validation.valid and result.validation.complete
    assert validate(snapshot, result.assignments).complete
    # The round's local optimum is not a bound for unrestricted global search.
    assert result.solver_status == 'FEASIBLE'
    assert result.best_bound is None
    assert result.objective_value == sum(result.metrics['weighted_objective_contributions'].values())
    assert result.snapshot_hash == snapshot_hash(snapshot)


def test_worse_round_compares_change_costs_to_original_draft(monkeypatch):
    snapshot = case(2, [shift(str(day), day, 8, 8) for day in range(9, 12)])
    snapshot.employees[0].target_minutes = 960
    snapshot.employees[1].target_minutes = 480
    snapshot.objectives = Objectives(
        hours=1, changes=1000, nights=0, weekends=0, holidays=0, wishes=0,
    )
    baseline, _, _ = controlled_run(monkeypatch, snapshot, repair=False)
    result, rounds, _ = controlled_run(
        monkeypatch, snapshot,
        round_assignments={('e0', demand.id) for demand in snapshot.demands},
    )
    traces = repair_trace(result)
    assert len(rounds) == len(traces) == 5
    assert baseline.validation.complete and result.validation.complete
    assert baseline.metrics['weighted_objective_contributions']['hours'] == 0
    assert baseline.metrics['weighted_objective_contributions']['changes'] == 3000
    # Moving a duty to e0 costs 960 in hours. Relative to the incumbent it
    # costs only 2000 in changes, falsely beating the original 3000. Relative
    # to the original empty draft, every complete plan costs 3000 in changes.
    assert all(trace['weighted_quality_cost'] == 3960 for trace in traces)
    assert all(trace['accepted'] is False for trace in traces)
    assert result.assignments == baseline.assignments
    assert result.metrics == baseline.metrics


def test_weekend_round_copies_segments_and_preserves_original_fixings(monkeypatch):
    snapshot = case(1, [shift(str(day), day, 8, 8) for day in range(8, 14)])
    snapshot.period_end = date(2026, 1, 13)
    snapshot.assignments = [Assignment(
        employee_id='e0', demand_id='10', fixed=True,
        segments=[segment.model_copy(deep=True) for segment in snapshot.shifts[2].segments],
    )]
    snapshot.objectives = Objectives(
        hours=0, changes=0, nights=0, weekends=0, holidays=0, wishes=0,
    )
    original = snapshot.model_dump_json()
    result, rounds, _ = controlled_run(monkeypatch, snapshot)
    candidate = rounds[0]['snapshot']
    traces = repair_trace(result)
    assert len(rounds) == len(traces) == 5
    trace = traces[0]
    assert trace['neighborhood'] == 'weekend'
    # Thursday and Tuesday are outside Friday--Monday; the original Saturday
    # fixing remains hard even though it lies within the selected weekend.
    assert {assignment.demand_id for assignment in candidate.assignments
            if not assignment.fixed} == {'9', '11', '12'}
    assert trace['released_assignments'] == 3
    assert {assignment.demand_id for assignment in result.assignments
            if assignment.fixed} == {'10'}
    duties = {duty.id: duty for duty in snapshot.shifts}
    for assignment in candidate.assignments:
        expected = duties[assignment.demand_id].segments
        assert assignment.segments == expected
        assert assignment.segments is not expected
        assert assignment.segments[0] is not expected[0]
    assert candidate.demands == snapshot.demands
    assert candidate.profiles == snapshot.profiles
    assert candidate.employees == snapshot.employees
    assert candidate.shifts == snapshot.shifts
    assert validate(snapshot, result.assignments).complete
    assert snapshot.model_dump_json() == original


def test_round_sequence_is_reproducible(monkeypatch):
    snapshot = case(8, [shift(str(day), day, 8, 8)
                        for day in [9, 10, 11, 12, 16, 17, 18, 19]])
    snapshot.period_end = date(2026, 1, 19)
    for demand in snapshot.demands:
        demand.minimum = demand.maximum = 8
    snapshot.objectives = Objectives(
        hours=0, changes=0, nights=0, weekends=0, holidays=0, wishes=0,
    )
    first, first_rounds, _ = controlled_run(monkeypatch, snapshot, outer_search_seconds=10)
    second, second_rounds, _ = controlled_run(monkeypatch, snapshot, outer_search_seconds=10)
    first_trace = repair_trace(first)
    assert len(first_trace) == len(first_rounds) == 6
    assert [entry['neighborhood'] for entry in first_trace] == ['weekend', 'employees'] * 3
    assert first_trace == repair_trace(second)
    assert first_rounds == second_rounds
    assert first.assignments == second.assignments
    for entry, round_call in zip(first_trace, first_rounds, strict=True):
        candidate = round_call['snapshot']
        released = [assignment for assignment in candidate.assignments if not assignment.fixed]
        assert entry['released_assignments'] == len(released)
        if entry['neighborhood'] == 'employees':
            selected_people = {assignment.employee_id for assignment in released}
            assert len(selected_people) == 6
            assert all(assignment.fixed is (assignment.employee_id not in selected_people)
                       for assignment in candidate.assignments)


def test_repair_accepts_improvement_with_unconfirmed_context(monkeypatch):
    snapshot = repair_case()
    snapshot.context_complete = False
    baseline, _, _ = controlled_run(monkeypatch, snapshot, repair=False, missing_demand='b')
    result, rounds, _ = controlled_run(monkeypatch, snapshot, missing_demand='b')
    assert baseline.validation.valid and not baseline.validation.complete
    assert any(diagnostic.code == 'context' for diagnostic in baseline.validation.diagnostics)
    assert baseline.metrics['vacancy_count'] == 1
    assert result.metrics['vacancy_count'] == 0
    assert result.vacancies == {}
    assert len(result.assignments) == 2
    assert result.validation.valid and not result.validation.complete
    assert any(diagnostic.code == 'context' for diagnostic in result.validation.diagnostics)
    checked = validate(snapshot, result.assignments)
    assert checked.valid and not checked.complete
    assert any(diagnostic.code == 'context' for diagnostic in checked.diagnostics)
    traces = repair_trace(result)
    assert len(rounds) == len(traces) == 5
    assert traces[0]['accepted'] is True
    assert all(trace['accepted'] is False for trace in traces[1:])
    assert result.metrics['objective_phase'] == 'repair'


def test_recursive_round_keeps_independent_hard_rule_validation(monkeypatch):
    snapshot = repair_case()
    baseline, _, _ = controlled_run(monkeypatch, snapshot, repair=False, missing_demand='b')
    result, rounds, rejected_plans = controlled_run(
        monkeypatch, snapshot, missing_demand='b', reject_full_round=True,
    )
    assert len(rounds) == len(repair_trace(result)) == 5
    assert rejected_plans
    assert not any(entry['accepted'] for entry in repair_trace(result))
    assert result.assignments == baseline.assignments
    assert result.metrics['vacancy_count'] == 1
    assert result.metrics['objective_phase'] == baseline.metrics['objective_phase']
    assert validate(snapshot, result.assignments).valid


@pytest.mark.parametrize('invalid_at', ['round_result', 'original_snapshot'])
def test_repair_rejects_hard_rule_violation_despite_fewer_vacancies(monkeypatch, invalid_at):
    snapshot = repair_case()
    snapshot.employees.append(snapshot.employees[0].model_copy(
        deep=True, update={'id': 'unapproved', 'approvals': []},
    ))
    invalid_rounds = []

    def corrupt_round(result):
        assert result.validation.valid
        assert result.metrics['vacancy_count'] == 0
        assert len(result.assignments) == 2
        # Cover both demands while assigning one duty to a person without
        # approval. The real validator rejects this improved coverage.
        invalid_assignments = [a.model_copy(deep=True) for a in result.assignments]
        invalid_assignments[0].employee_id = 'unapproved'
        checked = validate(snapshot, invalid_assignments)
        assert not checked.valid
        assert not any(diagnostic.code in ('vacancy', 'context')
                       for diagnostic in checked.diagnostics)
        if invalid_at == 'round_result':
            # An invalid round report alone must veto acceptance, even when
            # the original-snapshot check would approve the assignments.
            assert validate(snapshot, result.assignments).valid
            result.validation = checked
        else:
            # Keep the earlier valid report: only the fresh check against
            # the original snapshot can detect the corrupted assignments.
            result.assignments = invalid_assignments
        invalid_rounds.append(result.model_copy(deep=True))
        return result

    baseline, _, _ = controlled_run(monkeypatch, snapshot, repair=False, missing_demand='b')
    result, rounds, _ = controlled_run(
        monkeypatch, snapshot, missing_demand='b', round_result_transform=corrupt_round,
    )
    assert len(rounds) == len(invalid_rounds) == len(repair_trace(result)) == 5
    assert all(candidate.validation.valid is (invalid_at == 'original_snapshot')
               for candidate in invalid_rounds)
    assert all(candidate.metrics['vacancy_count'] < baseline.metrics['vacancy_count']
               for candidate in invalid_rounds)
    assert not any(entry['accepted'] for entry in repair_trace(result))
    assert result.assignments == baseline.assignments
    assert result.vacancies == baseline.vacancies
    assert result.metrics['vacancy_count'] == sum(result.vacancies.values()) == 1
    assert result.validation == baseline.validation
    assert result.metrics == baseline.metrics
    assert validate(snapshot, result.assignments).valid
