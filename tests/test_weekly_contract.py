"""Synthetic contractual workload: distinct from period target and hard maxima."""
from collections import Counter
from datetime import date

import pytest
from pydantic import ValidationError

from sp5generator.models import Assignment, Employee
from sp5generator.solver import solve
from sp5generator.sp5_adapter import import_snapshot
from sp5generator.validator import validate
from test_core_rules import case, shift
from test_sp5_adapter import SyntheticDatabase


@pytest.mark.parametrize('basis,expected', [(0, None), (1, 1200), (2, None), (3, None)])
def test_import_only_uses_active_weekly_basis(basis, expected):
    class Source(SyntheticDatabase):
        def get_employees(self, **kw):
            return [{**super().get_employees(**kw)[0], 'CALCBASE': basis,
                     'HRSWEEK': 20, 'HRSDAY': 4, 'HRSMONTH': 80, 'HRSTOTAL': 80}]
    snapshot = import_snapshot(Source(), date(2026, 2, 2), date(2026, 3, 1), '1', 'UTC')
    employee = snapshot.employees[0]
    assert employee.contractual_weekly_minutes == expected
    if basis == 1:
        assert employee.target_minutes == 80 * 60
    assert snapshot.profiles[0].max_weekly_minutes is None
    assert snapshot.metadata['provenance'][employee.id]['nominal_hours']['hours_week'] == 20


def test_legacy_employee_and_strict_weekly_minutes():
    data = case().employees[0].model_dump()
    data.pop('contractual_weekly_minutes')
    assert Employee.model_validate(data).contractual_weekly_minutes is None
    for invalid in (True, -1, 1.5):
        with pytest.raises(ValidationError):
            Employee.model_validate({**data, 'contractual_weekly_minutes': invalid})


def test_weekly_goal_balances_same_period_target_across_people_and_weeks():
    snapshot = case(2, [shift(str(day), day, 8, 10) for day in (5, 6, 7, 12, 13, 14)])
    snapshot.period_end = date(2026, 1, 18)
    for employee in snapshot.employees:
        employee.target_minutes = 30 * 60
        employee.contractual_weekly_minutes = 20 * 60
    snapshot.objectives.workday_transitions = 10
    legacy = snapshot.model_copy(deep=True)
    for employee in legacy.employees:
        employee.contractual_weekly_minutes = None
    concentrated = solve(legacy, 5)
    legacy_counts = Counter((a.employee_id, int(a.demand_id) >= 12) for a in concentrated.assignments)
    assert max(legacy_counts.values()) == 3
    result = solve(snapshot, 5)
    assert result.solver_status == 'OPTIMAL'
    assert validate(snapshot, result.assignments).valid
    assert len(result.assignments) == 6
    counts = Counter((a.employee_id, int(a.demand_id) >= 12) for a in result.assignments)
    assert max(counts.values()) == 2
    assert all(sum(counts[e.id, week] for week in (False, True)) == 3 for e in snapshot.employees)
    assert result.metrics['objective_contributions']['weekly_contract_excess'] == 0


@pytest.mark.parametrize('hard_max,expected', [(None, 3), (1200, 2)])
def test_contract_does_not_omit_demand_or_replace_hard_maximum(hard_max, expected):
    snapshot = case(1, [shift(str(day), day, 8, 10) for day in (5, 7, 9)])
    snapshot.employees[0].contractual_weekly_minutes = 1200
    snapshot.employees[0].target_minutes = 1800
    snapshot.profiles[0].max_weekly_minutes = hard_max
    result = solve(snapshot, 5, partial=True)
    assert result.validation.valid
    assert len(result.assignments) == expected


def test_fixed_work_counts_in_weekly_distribution_even_with_low_pay():
    snapshot = case(2, [shift('prior', 5, 8, 10), shift('new', 7, 8, 10)])
    snapshot.period_start = date(2026, 1, 7)
    snapshot.assignments = [Assignment(employee_id='e0', demand_id='prior', fixed=True)]
    snapshot.shifts[0].paid_minutes = 1
    for employee in snapshot.employees:
        employee.contractual_weekly_minutes = 600
        employee.target_minutes = 600
    result = solve(snapshot, 5)
    assert result.validation.valid
    assert next(a.employee_id for a in result.assignments if a.demand_id == 'new') == 'e1'
