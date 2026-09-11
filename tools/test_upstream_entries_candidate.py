"""Isolated candidate contract tests: synthetic only, no DBF/HTTP upstream access.

PYTHONPATH=<candidate library> .venv/bin/python -m pytest tools/test_upstream_entries_candidate.py
Set SP5_ENTRIES_ROUTER to the isolated candidate schedule.py for local ASGI tests.
"""
import ast
import os
import uuid
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.testclient import TestClient
from sp5lib.database import SP5Database


@pytest.fixture
def source():
    day = '2026-09-07'
    tables = {
        'MASHI': [
            {'ID': 1, 'EMPLOYEEID': 10, 'DATE': day, 'SHIFTID': 5, 'TYPE': 0},
            {'ID': 2, 'EMPLOYEEID': 10, 'DATE': day, 'SHIFTID': 6, 'TYPE': 0},
            {'ID': 3, 'EMPLOYEEID': 10, 'DATE': day, 'SHIFTID': 7, 'TYPE': 1},
        ],
        'SPSHI': [
            {'ID': 8, 'EMPLOYEEID': 10, 'DATE': day, 'SHIFTID': 5, 'TYPE': 1,
             'STARTEND': '0800-1000', 'DURATION': 2},
            {'ID': 9, 'EMPLOYEEID': 10, 'DATE': day, 'SHIFTID': 0, 'TYPE': 0,
             'STARTEND': '1600-1900', 'DURATION': 3},
        ],
        'ABSEN': [{'ID': 11, 'EMPLOYEEID': 10, 'DATE': day, 'LEAVETYPID': 7,
                   'INTERVAL': 3, 'START': 600, 'END': 660}],
    }
    db = object.__new__(SP5Database)
    db.db_path = f'synthetic-entries-{uuid.uuid4()}'
    db._read = lambda table: tables.get(table, [])
    db.get_employees = lambda **kwargs: [
        {'ID': 10, 'NAME': 'Synthetic', 'SHORTNAME': 'S'},
        {'ID': 20, 'NAME': 'Free', 'SHORTNAME': 'F'},
    ]
    db.get_shifts = lambda **kwargs: [
        {'ID': sid, 'NAME': f'Shift {sid}', 'SHORTNAME': f'S{sid}',
         **{f'STARTEND{i}': '08:00-16:00' for i in range(8)},
         **{f'DURATION{i}': 6 for i in range(8)}} for sid in (5, 6, 7)
    ]
    db.get_workplaces = lambda **kwargs: []
    db.get_leave_types = lambda **kwargs: [{'ID': 7, 'NAME': 'Synthetic leave'}]
    db.get_group_members = lambda group_id: [10] if group_id == 1 else [20]
    db._anon_display = lambda: {'short': 'X', 'name': 'Absent', 'color_bk': '#FFFFFF',
                                'color_text': '#000000', 'bold': False}
    return db, tables


@pytest.mark.parametrize('plan,ids', [('ist', [1, 2]), ('soll', [3]), ('both', [1, 2, 3])])
@pytest.mark.parametrize('reverse', [False, True])
def test_source_rows_survive_plan_selection_and_reordering(source, plan, ids, reverse):
    db, tables = source
    if reverse:
        for rows in tables.values():
            rows.reverse()
    result = db.get_schedule_entries('2026-09-07', plan=plan, week=True)
    assert result['entry_semantics'] == 'source_records_not_work_totals'
    rows = result['days'][0]['entries']
    normals = [r for r in rows if r['kind'] == 'shift']
    assert sorted(r['source_id'] for r in normals) == ids
    assert all(r['replaced_in_ist'] == (r['schedule_type'] == 0) for r in normals)
    assert all((r['startend'], r['duration']) == ('08:00-16:00', 6) for r in normals)
    assert sorted((r['source_id'], r['startend'], r['duration']) for r in rows
                  if r['kind'] == 'special_shift') == [(8, '0800-1000', 2), (9, '1600-1900', 3)]
    absence = next(r for r in rows if r['kind'] == 'absence')
    assert (absence['interval'], absence['start_time'], absence['end_time']) == (3, 600, 660)
    assert [r['employee_id'] for r in rows if r['kind'] is None] == [20]
    assert all(len(day['entries']) == 2 for day in result['days'][1:])


def test_week_crosses_month_and_year_without_duplicate_rows(source):
    db, tables = source
    tables['SPSHI'] = tables['ABSEN'] = []
    tables['MASHI'] = [
        {'ID': i, 'EMPLOYEEID': 10, 'DATE': day, 'SHIFTID': 5, 'TYPE': 0}
        for i, day in enumerate(['2026-12-28', '2026-12-31', '2027-01-01', '2027-01-03'])
    ]
    result = db.get_schedule_entries('2027-01-01', plan='ist', week=True)
    assert (result['week_start'], result['week_end']) == ('2026-12-28', '2027-01-03')
    rows = [r for d in result['days'] for r in d['entries'] if r['kind'] == 'shift']
    assert sorted(r['source_id'] for r in rows) == [0, 1, 2, 3]


def test_missing_special_time_is_not_fabricated(source):
    db, tables = source
    del tables['SPSHI'][0]['STARTEND']
    del tables['SPSHI'][0]['DURATION']
    rows = db.get_schedule_entries('2026-09-07', plan='ist')['days'][0]['entries']
    row = next(r for r in rows if r.get('source_id') == 8)
    assert row['startend'] is None and row['duration'] is None
    assert all(r['replaced_in_ist'] for r in rows if r['kind'] == 'shift')


def test_legacy_month_day_week_payloads_unchanged(source):
    db, _ = source
    assert all('source_table' not in r for r in db.get_schedule(2026, 9))
    day = db.get_schedule_day('2026-09-07')
    week = db.get_schedule_week('2026-09-07')
    assert len(day) == 2
    assert day[0]['kind'] == 'absence'  # Legacy remains explicitly lossy.
    assert 'interval' not in day[0]
    assert week['days'][0]['entries'][0]['kind'] == 'absence'


def test_cycle_is_not_suppressed_by_alternative_soll(source):
    db, tables = source
    tables['SPSHI'] = tables['ABSEN'] = []
    tables['MASHI'] = [tables['MASHI'][2]]
    tables.update({
        'CYCLE': [{'ID': 1, 'SIZE': 1, 'UNIT': 0}],
        'CYENT': [{'CYCLEEID': 1, 'INDEX': 0, 'SHIFTID': 5}],
        'CYASS': [{'EMPLOYEEID': 10, 'CYCLEID': 1, 'START': '2026-09-07',
                   'END': '2026-09-07', 'ENTRANCE': 0}],
    })
    rows = db.get_schedule_entries('2026-09-07', plan='both')['days'][0]['entries']
    assert sorted(r['shift_id'] for r in rows if r['kind'] == 'shift') == [5, 7]
    cycle = next(r for r in rows if r.get('source') == 'cycle')
    assert cycle['source_table'] == 'CYASS' and cycle['source_id'] is None


@pytest.fixture
def client(source):
    router_path = os.environ.get('SP5_ENTRIES_ROUTER')
    if not router_path:
        pytest.fail('SP5_ENTRIES_ROUTER must identify the isolated candidate, not production')
    db, _ = source
    tree = ast.parse(Path(router_path).read_text())
    names = ('get_schedule_day', 'get_schedule_week')
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert len(nodes) == 2
    for node in nodes:
        node.decorator_list = []
    namespace = {'Query': Query, 'Depends': Depends, 'HTTPException': HTTPException,
                 'absence_visibility_mode': lambda: 0,
                 'visible_employee_ids': lambda: None, 'get_db': lambda: db}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(router_path), 'exec'), namespace)
    app = FastAPI()
    for name in names:
        app.get('/' + name.removeprefix('get_schedule_'))(namespace[name])
    return TestClient(app), app, namespace


@pytest.mark.parametrize('endpoint', ['day', 'week'])
@pytest.mark.parametrize('mode', [0, 1, 2])
def test_api_scope_and_absence_visibility(client, endpoint, mode):
    http, app, namespace = client
    app.dependency_overrides[namespace['visible_employee_ids']] = lambda: {10}
    app.dependency_overrides[namespace['absence_visibility_mode']] = lambda: mode
    response = http.get(f'/{endpoint}?date=2026-09-07&plan=both')
    assert response.status_code == 200
    data = response.json()
    rows = data if endpoint == 'day' else data['days'][0]['entries']
    assert {r['employee_id'] for r in rows} == {10}
    assert len([r for r in rows if r['kind'] == 'shift']) == 3
    absences = [r for r in rows if r['kind'] == 'absence']
    if mode == 2:
        assert not absences
    else:
        assert len(absences) == 1
        if mode == 1:
            assert absences[0]['leave_type_id'] is None
            assert absences[0]['leave_name'] == 'Absent'


@pytest.mark.parametrize('endpoint', ['day', 'week'])
def test_api_bad_plan_empty_scope_group_and_legacy(client, endpoint):
    http, app, namespace = client
    assert http.get(f'/{endpoint}?date=2026-09-07&plan=unknown').status_code == 400
    assert http.get(f'/{endpoint}?date=not-a-date&plan=ist').status_code == 400
    legacy = http.get(f'/{endpoint}?date=2026-09-07').json()
    legacy_rows = legacy if endpoint == 'day' else legacy['days'][0]['entries']
    assert len(legacy_rows) == 2 and legacy_rows[0]['kind'] == 'absence'
    group = http.get(f'/{endpoint}?date=2026-09-07&plan=ist&group_id=2').json()
    group_rows = group if endpoint == 'day' else group['days'][0]['entries']
    assert len(group_rows) == 1 and group_rows[0]['employee_id'] == 20
    app.dependency_overrides[namespace['visible_employee_ids']] = lambda: set()
    empty = http.get(f'/{endpoint}?date=2026-09-07&plan=ist').json()
    assert (empty if endpoint == 'day' else empty['days'][0]['entries']) == []
