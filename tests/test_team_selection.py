"""Synthetic exact team selection and history-only functions."""
from datetime import date

import pytest

from sp5generator.hierarchy import resolve_group_selection

GROUPS = [{"ID": 1}, {"ID": 2, "SUPERID": 1}, {"ID": 3, "SUPERID": 1}]


def test_exact_selection_and_legacy_subtree():
    assert resolve_group_selection(GROUPS, team_id="1") == [1, 2, 3]
    assert resolve_group_selection(GROUPS, team_ids=["3", "sp5:group:1", "3"]) == [1, 3]
    for selection in ([], ["99"]):
        with pytest.raises(ValueError):
            resolve_group_selection(GROUPS, team_ids=selection)
    with pytest.raises(ValueError):
        resolve_group_selection(GROUPS)
    with pytest.raises(ValueError):
        resolve_group_selection(GROUPS, team_id="1", team_ids=["2"])


def test_exact_import_shared_person_and_history_without_demand():
    pytest.importorskip("sp5lib")
    from test_sp5_adapter import SyntheticDatabase
    from sp5generator.sp5_adapter import historical_matrix, import_snapshot

    class Source(SyntheticDatabase):
        def get_groups(self):
            return GROUPS

        def get_group_members(self, gid):
            return [101] if gid in (2, 3) else []

        def get_employee_groups(self, eid):
            return [2, 3]

        def get_staffing_requirements(self):
            row = super().get_staffing_requirements()["shift_requirements"][0]
            return {"shift_requirements": [{**row, "group_id": 2}]}

        def get_schedule(self, year, month, group_id=None, **kwargs):
            if (year, month) != (2026, 1):
                return []
            return [{"employee_id": 101, "date": "2026-01-02", "kind": "shift", "shift_id": 201, "workplace_id": 301}]

    db = Source()
    snapshot = import_snapshot(db, date(2026, 1, 6), date(2026, 1, 6), timezone="UTC", team_ids=["1", "3"])
    assert snapshot.metadata["selected_group_ids"] == [1, 3]
    assert len(snapshot.employees) == 1
    assert not [d for d in snapshot.demands if d.source == "sp5:SHDEM"]
    assert len(snapshot.metadata["context_schedule"]) == 1
    original_demands = list(snapshot.demands)
    history = historical_matrix(db, snapshot, date(2026, 1, 1), date(2026, 1, 5))
    assert history[0]["observed_assignment_count"] == 1
    assert history[0]["suggested_approvals"][0]["confirmed"] is False
    assert any(p.function_id == "sp5:service:201" for p in snapshot.positions)
    assert not snapshot.employees[0].approvals
    assert not [d for d in snapshot.demands if d.source == "sp5:SHDEM"]
    assert snapshot.demands == original_demands
    count = len(snapshot.positions)
    historical_matrix(db, snapshot, date(2026, 1, 1), date(2026, 1, 5))
    assert len(snapshot.positions) == count


def test_api_exact_selection_does_not_query_excluded_subtree(monkeypatch):
    pytest.importorskip("sp5lib")
    from test_sp5_adapter import SyntheticDatabase
    from sp5generator.api_adapter import import_api

    source = SyntheticDatabase()
    calls = []

    class Client:
        def authorize(self):
            pass

        def verify(self):
            return "synthetic"

        def get(self, path, **params):
            calls.append((path, params))
            if path == "/api/groups":
                return GROUPS
            if path.startswith("/api/groups/"):
                assert path != "/api/groups/2/members"
                return source.get_employees() if "/3/" in path else []
            if path == "/api/schedule":
                assert params["group_id"] in (1, 3)
                return []
            return {
                "/api/employees": source.get_employees(),
                "/api/shifts": source.get_shifts(),
                "/api/workplaces": source.get_workplaces(),
                "/api/holidays": source.get_holidays(),
                "/api/staffing-requirements": source.get_staffing_requirements(),
                "/api/staffing-requirements/special": [],
                "/api/restrictions": [],
            }[path]

    monkeypatch.setattr("sp5generator.api_adapter.APIClient", Client)
    snapshot = import_api(date(2026, 1, 6), date(2026, 1, 6), timezone="UTC", team_ids=["1", "3"])
    assert snapshot.metadata["selected_group_ids"] == [1, 3]
    assert len(snapshot.employees) == 1
    assert snapshot.employees[0].team_ids == ["sp5:group:3"]
    assert snapshot.metadata["history_period"] == {"start": "2025-10-08", "end": "2026-01-05"}
