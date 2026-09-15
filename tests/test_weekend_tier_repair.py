"""Repair acceptance keeps coverage and weekend coupling ahead of soft goals."""

from ortools.sat.python import cp_model

from sp5generator import solver
from sp5generator.models import Assignment, Objectives
from sp5generator.validator import validate
from test_core_rules import case, shift


COUPLED = {('e0', 'sat'), ('e0', 'sun')}
SPLIT = {('e0', 'sat'), ('e1', 'sun')}


def weekend_case(assignments, *, split_weekends=1):
    snapshot = case(2, [shift('sat', 10, 8, 8), shift('sun', 11, 8, 8)])
    for employee in snapshot.employees:
        employee.target_minutes = 480
    snapshot.objectives = Objectives(**{
        field: 0 for field in Objectives.model_fields
    })
    snapshot.objectives.hours = 1
    snapshot.objectives.split_weekends = split_weekends
    snapshot.assignments = [
        Assignment(employee_id=employee, demand_id=demand)
        for employee, demand in sorted(assignments)
    ]
    return snapshot


def controlled_repair(monkeypatch, snapshot, initial, candidate):
    """Use real CP-SAT candidates with deterministic search and round budgets.

    Restrict searches to explicit valid assignments to exercise acceptance of
    both improving and worsening neighborhoods. Report the restricted outer
    search as feasible so it cannot claim an unrestricted coupling proof.
    """
    real_solve = solver.solve
    real_search = cp_model.CpSolver.solve
    elapsed = [0.0]
    inside_round = [False]

    def search(self, model, *args, **kwargs):
        if self.parameters.fix_variables_to_their_hinted_value:
            return real_search(self, model, *args, **kwargs)
        restricted = model.clone()
        selected = candidate if inside_round[0] else initial
        selected_names = {f'assign:{employee}:{demand}' for employee, demand in selected}
        for index, variable in enumerate(restricted.proto.variables):
            if variable.name.startswith('assign:'):
                restricted.add(restricted.get_int_var_from_proto_index(index)
                               == int(variable.name in selected_names))
        status = real_search(self, restricted, *args, **kwargs)
        assert status == cp_model.OPTIMAL
        if not inside_round[0]:
            elapsed[0] += 10
            return cp_model.FEASIBLE
        return status

    def recursive_solve(source, time_limit=30, partial=False, _repair=True, workers=None):
        assert partial and not _repair and not inside_round[0]
        inside_round[0] = True
        try:
            result = real_solve(source, time_limit, partial=partial, _repair=_repair)
        finally:
            inside_round[0] = False
        elapsed[0] += time_limit
        return result

    monkeypatch.setattr(solver, 'monotonic', lambda: elapsed[0])
    monkeypatch.setattr(cp_model.CpSolver, 'solve', search)
    monkeypatch.setattr(solver, 'solve', recursive_solve)
    return real_solve(snapshot, time_limit=120, partial=True)


def repair_trace(result):
    traces = [entry for entry in result.parameters['search_trace']
              if entry['phase'] == 'repair']
    assert traces
    return traces


def selected(result):
    return {(assignment.employee_id, assignment.demand_id)
            for assignment in result.assignments}


def test_repair_rejects_split_weekend_despite_better_hours(monkeypatch):
    snapshot = weekend_case(COUPLED)
    result = controlled_repair(monkeypatch, snapshot, COUPLED, SPLIT)
    assert selected(result) == COUPLED
    assert result.metrics['vacancy_count'] == 0
    assert result.metrics['objective_contributions']['split_weekends'] == 0
    assert sorted(employee['paid_minutes'] for employee in result.metrics['employees'].values()) == [
        0, 960,
    ]
    assert all(not trace['accepted'] for trace in repair_trace(result))
    assert all(trace['split_weekend_count'] == 2 for trace in repair_trace(result))
    assert result.parameters['split_weekend_count'] == 0
    assert result.parameters['split_weekends_proven']
    assert validate(snapshot, result.assignments).complete


def test_repair_accepts_coupling_despite_worse_hours(monkeypatch):
    snapshot = weekend_case(SPLIT)
    result = controlled_repair(monkeypatch, snapshot, SPLIT, COUPLED)
    assert selected(result) == COUPLED
    assert result.metrics['vacancy_count'] == 0
    assert result.metrics['objective_contributions']['split_weekends'] == 0
    assert sorted(employee['paid_minutes'] for employee in result.metrics['employees'].values()) == [
        0, 960,
    ]
    assert repair_trace(result)[0]['accepted']
    assert result.metrics['objective_phase'] == 'repair'
    assert result.parameters['split_weekend_count'] == 0
    assert result.parameters['split_weekends_proven']
    assert validate(snapshot, result.assignments).complete


def test_repair_accepts_coverage_even_with_more_split_weekends(monkeypatch):
    initial = {('e0', 'sat')}
    snapshot = weekend_case(initial)
    result = controlled_repair(monkeypatch, snapshot, initial, SPLIT)
    assert selected(result) == SPLIT
    assert result.vacancies == {}
    assert result.metrics['vacancy_count'] == 0
    assert result.metrics['objective_contributions']['split_weekends'] == 2
    assert repair_trace(result)[0]['accepted']
    assert result.parameters['coverage_proven']
    assert result.parameters['split_weekend_count'] == 2
    assert not result.parameters['split_weekends_proven']
    assert validate(snapshot, result.assignments).complete


def test_repair_ignores_weekend_splits_when_goal_disabled(monkeypatch):
    snapshot = weekend_case(COUPLED, split_weekends=0)
    result = controlled_repair(monkeypatch, snapshot, COUPLED, SPLIT)
    assert selected(result) == SPLIT
    assert result.metrics['vacancy_count'] == 0
    assert sorted(employee['paid_minutes'] for employee in result.metrics['employees'].values()) == [
        480, 480,
    ]
    assert repair_trace(result)[0]['accepted']
    assert all(trace['split_weekend_count'] == 0 for trace in repair_trace(result))
    assert all(trace['phase'] != 'couple' for trace in result.parameters['search_trace'])
    assert validate(snapshot, result.assignments).complete
