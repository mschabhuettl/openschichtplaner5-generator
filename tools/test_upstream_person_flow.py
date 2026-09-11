"""Characterize unresolved person loss; passing tests do not endorse this behavior.

Synthetic records only. SP5_API_SOURCE selects the unmodified API checkout.
Use the existing AST-isolation approach to avoid production startup/config.
"""
import ast
import os
from datetime import date
from pathlib import Path

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from sp5lib.database import SP5Database

from sp5generator.api_adapter import _Database
from sp5generator.sp5_adapter import import_snapshot
from tests.test_sp5_adapter import SyntheticDatabase


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    db = SP5Database(str(tmp_path))
    employees = SyntheticDatabase().get_employees()
    assignments = [{'GROUPID': 1, 'EMPLOYEEID': 101}]
    monkeypatch.setattr(db, '_read', lambda table: assignments if table == 'GRASG' else [])
    monkeypatch.setattr(db, 'get_employees', lambda **kw: employees)
    path = Path(os.environ['SP5_API_SOURCE']) / 'sp5api/routers/employees.py'
    nodes = [n for n in ast.parse(path.read_text()).body
             if isinstance(n, ast.FunctionDef) and n.name == 'get_group_members']
    assert len(nodes) == 1
    ns = {'router': APIRouter(), 'get_db': lambda: db}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), ns)
    app = FastAPI()
    app.include_router(ns['router'])
    with TestClient(app) as http:
        class Client:
            def get(self, path, **params):
                if path == '/api/employees':
                    return employees
                response = http.get(path, params=params)
                assert response.status_code == 200
                return response.json()

        yield db, _Database(Client(), 1), employees, assignments


def test_orphan_membership_disappears_before_generator_completeness_check(pipeline):
    db, adapter, employees, assignments = pipeline
    assignments.append({'GROUPID': 1, 'EMPLOYEEID': 102})
    assert db.get_group_members(1) == [101, 102]
    assert adapter.get_group_members(1) == [101]
    # This is the current import_from_api preflight: it cannot detect the loss.
    assert set(adapter.get_group_members(1)) <= {e['ID'] for e in adapter.get_employees()}


def test_conflicting_employee_rows_are_last_wins_in_api_and_generator(pipeline):
    _, adapter, employees, _ = pipeline
    employees.append({**employees[0], 'HRSWEEK': 12, 'EMPEND': '2026-01-02'})
    assert adapter.client.get('/api/groups/1/members') == [employees[-1]]
    source = SyntheticDatabase()
    source.get_employees = lambda **kw: employees
    with pytest.raises(ValueError, match='conflicting_employee'):
        import_snapshot(source, date(2026, 1, 5), date(2026, 1, 6), '1', 'UTC')


def test_valid_repeated_membership_does_not_duplicate_generator_person(pipeline):
    db, adapter, _, assignments = pipeline
    assignments.append({'GROUPID': 1, 'EMPLOYEEID': 101})
    assert db.get_group_members(1) == adapter.get_group_members(1) == [101, 101]
    source = SyntheticDatabase()
    source.get_group_members = adapter.get_group_members
    snapshot = import_snapshot(source, date(2026, 1, 5), date(2026, 1, 6), '1', 'UTC')
    assert len(snapshot.employees) == 1


def test_direct_library_import_rejects_orphan_with_specific_diagnostic():
    source = SyntheticDatabase()
    source.get_group_members = lambda group: [101, 102]
    with pytest.raises(ValueError, match='orphan_membership'):
        import_snapshot(source, date(2026, 1, 5), date(2026, 1, 6), '1', 'UTC')
