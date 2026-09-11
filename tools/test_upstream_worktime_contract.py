"""Synthetic HTTP boundary tests for the consolidated, isolated upstream candidate.

No production router startup, customer records, network or persistent config.
Set SP5_WORK_TIME_ROUTER to the patched candidate work_time_rules.py.
"""
import ast
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

import pytest
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.testclient import TestClient
from sp5lib import calculations as calc


@pytest.fixture
def setup():
    tables = {
        'MASHI': [
            {'EMPLOYEEID': 10, 'DATE': '2026-09-07', 'SHIFTID': 1, 'TYPE': 0},
            {'EMPLOYEEID': 10, 'DATE': '2026-09-07', 'SHIFTID': 2, 'TYPE': 1},
        ],
        'SHIFT': [
            {'ID': sid, **{f'DURATION{i}': hours for i in range(8)},
             **{f'STARTEND{i}': times for i in range(8)}}
            for sid, hours, times in [(1, 8, '08:00-16:00'), (2, 9, '08:00-17:00')]
        ],
    }
    employees = [{'ID': 10, 'GROUPID': 1}]
    db = SimpleNamespace(_read=lambda table: tables.get(table, []),
                         get_employee=lambda eid: next((e for e in employees if e['ID'] == eid), None),
                         get_employees=lambda **kwargs: employees)
    defaults = {'max_hours_per_day': 10, 'max_hours_per_week': 48,
                'min_rest_hours_between_shifts': 11, 'max_consecutive_days': 6,
                'enabled': True}
    path = Path(os.environ['SP5_WORK_TIME_ROUTER'])
    nodes = [node for node in ast.parse(path.read_text()).body
             if isinstance(node, ast.FunctionDef)
             and node.name not in ('_load_rules', '_save_rules', 'get_rules', 'update_rules')]
    for node in nodes:
        node.decorator_list = []
    scope = lambda: None  # noqa: E731
    ns = {'date': date, 'datetime': datetime, 'timedelta': timedelta, 'calc': calc,
          'Query': Query, 'Depends': Depends, 'HTTPException': HTTPException, 'Literal': Literal,
          'require_planer': lambda: {}, 'visible_employee_ids': scope,
          'get_db': lambda: db, '_load_rules': lambda: dict(defaults),
          'filter_by_employee_scope': lambda rows, ids: [e for e in rows if ids is None or e['ID'] in ids]}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), ns)
    app = FastAPI()
    app.post('/check')(ns['check_employee'])
    app.post('/check-all')(ns['check_all'])
    return TestClient(app), app, ns, tables, employees, defaults


def check(setup, endpoint='check', **overrides):
    params = {'from': '2026-09-07', 'to': '2026-09-07', **overrides}
    if endpoint == 'check':
        params.setdefault('employee_id', 10)
    return setup[0].post('/' + endpoint, params=params)


@pytest.mark.parametrize('endpoint', ['check', 'check-all'])
@pytest.mark.parametrize('plan,hours', [('ist', 8), ('soll', 9), (None, 17)])
def test_http_selected_plan_and_explicit_incompleteness(setup, endpoint, plan, hours):
    params = {'max_hours_per_day': 6}
    if plan:
        params['plan'] = plan
    response = check(setup, endpoint, **params)
    assert response.status_code == 200
    result = response.json()
    assert [v['value'] for v in result['violations'] if v['type'] == 'max_hours_per_day'] == [hours]
    assert result['coverage'] == {
        'contract': 'work-time-diagnostic-v1', 'plan': plan or 'legacy_mixed',
        'from': '2026-09-07', 'to': '2026-09-07', 'complete': False,
        'reasons': ['paid_hours_not_elapsed_work', 'unsplit_calendar_totals',
                    'timezone_unresolved', 'boundary_context_not_loaded',
                    'effective_segments_unresolved'] + ([] if plan else ['legacy_mixed_plan_sources']),
    }


@pytest.mark.parametrize('endpoint', ['check', 'check-all'])
def test_http_bad_plan_scope_and_range(setup, endpoint):
    for plan in ['both', 'unknown']:
        assert check(setup, endpoint, plan=plan).status_code == 422
    assert check(setup, endpoint, **{'to': '2026-09-06'}).status_code == 422
    setup[1].dependency_overrides[setup[2]['visible_employee_ids']] = lambda: set()
    response = check(setup, endpoint, plan='ist')
    if endpoint == 'check':
        assert response.status_code == 404
    else:
        assert response.json()['violations'] == []
        assert response.json()['coverage']['complete'] is False


@pytest.mark.parametrize('special_type', [0, 1])
def test_special_is_actual_source_not_mashi_type_semantics(setup, special_type):
    setup[3]['SPSHI'] = [{'EMPLOYEEID': 10, 'DATE': '2026-09-07',
                          'TYPE': special_type, 'SHIFTID': 1,
                          'STARTEND': '18:00-20:00', 'DURATION': 2}]
    for plan, hours in [('ist', 2), ('soll', 9)]:
        result = check(setup, plan=plan, max_hours_per_day=1).json()
        assert [v['value'] for v in result['violations'] if v['type'] == 'max_hours_per_day'] == [hours]


def test_soll_does_not_suppress_ist_cycle_or_invent_soll_cycle(setup):
    tables = setup[3]
    tables['MASHI'] = [tables['MASHI'][1]]
    tables.update({'CYCLE': [{'ID': 1, 'SIZE': 1, 'UNIT': 0}],
                   'CYENT': [{'CYCLEEID': 1, 'INDEX': 0, 'SHIFTID': 1}],
                   'CYASS': [{'EMPLOYEEID': 10, 'CYCLEID': 1, 'START': '2026-09-07',
                              'END': '2026-09-07', 'ENTRANCE': 0}]})
    for plan, hours in [('ist', 8), ('soll', 9)]:
        result = check(setup, plan=plan, max_hours_per_day=6).json()
        assert [v['value'] for v in result['violations'] if v['type'] == 'max_hours_per_day'] == [hours]
    tables['MASHI'] = []
    assert check(setup, plan='soll').json()['violations'] == []


def test_overlap_and_unresolved_model_are_connected_to_same_selected_plan(setup):
    setup[3]['MASHI'].append({**setup[3]['MASHI'][1], 'TYPE': 0})
    result = check(setup, plan='ist', week_limit_mode='model').json()
    assert {'shift_overlap', 'weekly_model_unresolved'} <= {v['type'] for v in result['violations']}
    assert 'weekly_model_unresolved' in result['coverage']['reasons']
    soll = check(setup, plan='soll', week_limit_mode='fixed').json()
    assert soll['violations'] == []
    assert soll['coverage']['complete'] is False


def test_disabled_rules_cannot_report_complete_check(setup):
    setup[5]['enabled'] = False
    result = check(setup, plan='ist').json()
    assert result['violations'] == []
    assert result['summary']['total'] == 0
    assert result['coverage']['complete'] is False
    assert 'rules_disabled' in result['coverage']['reasons']


def test_group_filter_does_not_leak_other_employee_violations(setup):
    setup[4].append({'ID': 20, 'GROUPID': 2})
    result = check(setup, 'check-all', plan='ist', group_id=2, max_hours_per_day=1).json()
    assert result['violations'] == []
    assert result['coverage']['complete'] is False
