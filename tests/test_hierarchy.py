"""Synthetic hierarchical groups, memberships and duties."""

from datetime import date
import pytest

from sp5generator.hierarchy import group_tree, selected_group_ids


def test_tree_handles_unordered_descendants_and_missing_visible_parent():
    groups = [
        {"ID": 3, "SUPERID": 2},
        {"ID": 1},
        {"ID": 2, "SUPERID": 1},
        {"ID": 4, "SUPERID": 99},
    ]
    assert selected_group_ids(groups, 1) == [1, 2, 3]
    assert [(g["id"], g["depth"]) for g in group_tree(groups)] == [
        ("1", 0),
        ("2", 1),
        ("3", 2),
        ("4", 0),
    ]
    assert selected_group_ids(groups, 2) == [2, 3]
    with pytest.raises(ValueError):
        selected_group_ids(groups, 99)


@pytest.mark.parametrize(
    "groups",
    [
        [{"ID": 1, "SUPERID": 1}],
        [{"ID": 1, "SUPERID": 2}, {"ID": 2, "SUPERID": 1}],
        [{"ID": 1}, {"ID": 1}],
    ],
)
def test_malformed_tree_rejected(groups):
    with pytest.raises(ValueError):
        group_tree(groups)


def test_parent_import_includes_children_preserves_demand_teams_and_deduplicates():
    pytest.importorskip("sp5lib")
    from test_sp5_adapter import SyntheticDatabase
    from sp5generator.sp5_adapter import import_snapshot, historical_matrix

    class TreeDatabase(SyntheticDatabase):
        def get_groups(self):
            return [
                {"ID": 1, "NAME": "Team A"},
                {"ID": 2, "SUPERID": 1, "NAME": "Team B"},
                {"ID": 3, "SUPERID": 2, "NAME": "Team C"},
            ]

        def get_group_members(self, gid):
            return [] if gid == 1 else [101]

        def get_employee_groups(self, eid):
            return [2, 3]

        def get_staffing_requirements(self):
            row = super().get_staffing_requirements()["shift_requirements"][0]
            return {
                "shift_requirements": [
                    {**row, "id": 402, "group_id": 2},
                    {**row, "id": 403, "group_id": 3},
                ]
            }

        def get_schedule(self, year, month, group_id=None, **kwargs):
            if month != 1 or group_id == 1:
                return []
            return [
                {
                    "employee_id": 101,
                    "date": "2026-01-02",
                    "kind": "shift",
                    "shift_id": 201,
                    "workplace_id": 301,
                }
            ]

    db = TreeDatabase()
    snapshot = import_snapshot(db, date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert len(snapshot.employees) == 1
    assert snapshot.employees[0].team_ids == ["sp5:group:2", "sp5:group:3"]
    regular = [s for s in snapshot.shifts if s.source == "sp5:SHIFT"]
    assert {s.team_id for s in regular} == {"sp5:group:2", "sp5:group:3"}
    assert len(snapshot.assignments) == 1
    assert len(snapshot.metadata["context_schedule"]) == 1
    assert len(snapshot.restrictions) == 2
    history = historical_matrix(db, snapshot, date(2026, 1, 1), date(2026, 1, 5))
    assert history[0]["observed_assignment_count"] == 1
