"""Synthetic opt-in API join correction; no source state or startup services."""
import ast
import os
from pathlib import Path
import subprocess

import pytest
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.testclient import TestClient


@pytest.mark.parametrize('case', ['valid', 'repeat_member', 'repeat_employee', 'orphan',
                                  'conflict', 'conflict_reversed'])
def test_person_join_candidate(tmp_path, case):
    target = tmp_path / 'sp5api/routers/employees.py'
    target.parent.mkdir(parents=True)
    target.write_text((Path(os.environ['SP5_API_SOURCE']) /
                       'sp5api/routers/employees.py').read_text())
    patch = Path(__file__).with_name('upstream-api-person-integrity-candidate.patch')
    subprocess.run(['git', 'apply', '--directory=' + str(tmp_path),
                    '--unsafe-paths', str(patch)], check=True, capture_output=True)
    nodes = [n for n in ast.parse(target.read_text()).body
             if isinstance(n, ast.FunctionDef) and n.name == 'get_group_members']
    assert len(nodes) == 1
    record = {'ID': 101, 'NAME': 'PRIVATE_SENTINEL', 'HRSWEEK': 40, 'EMPEND': ''}
    employees, members = [record], [101]
    if case == 'repeat_member':
        members.append(101)
    if case == 'repeat_employee':
        employees.append(dict(record))
    if case == 'orphan':
        members.append(102)
    if case.startswith('conflict'):
        employees.append({**record, 'HRSWEEK': 12, 'EMPEND': '2026-01-02'})
        if case.endswith('reversed'):
            employees.reverse()

    class Database:
        def get_group_members(self, group_id):
            assert group_id == 1
            return members

        def get_employees(self, include_hidden):
            assert include_hidden
            return employees

    ns = {'router': APIRouter(), 'get_db': Database, 'HTTPException': HTTPException}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(target), 'exec'), ns)
    app = FastAPI()
    app.include_router(ns['router'])
    route = '/api/groups/1/members'
    with TestClient(app) as client:
        response = client.get(route)
    if case == 'orphan' or case.startswith('conflict'):
        assert response.status_code == 500
        assert response.headers['X-SP5-Error-Code'] == 'employee_source_unresolved'
        assert response.headers['X-SP5-Error-Category'] == (
            'orphan_membership' if case == 'orphan' else 'conflicting_employee')
        assert 'PRIVATE_SENTINEL' not in response.text
        assert '101' not in response.text and '102' not in response.text
        assert '2026' not in response.text and str(tmp_path) not in response.text
    else:
        assert response.status_code == 200
        assert response.json() == [record] * len(members)
