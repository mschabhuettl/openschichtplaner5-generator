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


@pytest.mark.parametrize("group_id", [0, -1, 1.5, True, "1.0", None])
def test_invalid_or_reserved_group_ids_are_rejected(group_id):
    with pytest.raises(ValueError, match="ungültige ID"):
        group_tree([{"ID": group_id}])


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
    assert snapshot.employees[0].team_ids == ["sp5:group:1", "sp5:group:2", "sp5:group:3"]
    regular = [s for s in snapshot.shifts if s.source == "sp5:SHIFT"]
    assert {s.team_id for s in regular} == {"sp5:group:2", "sp5:group:3"}
    assert len(snapshot.assignments) == 1
    assert len(snapshot.metadata["context_schedule"]) == 1
    assert len(snapshot.restrictions) == 2
    history = historical_matrix(db, snapshot, date(2026, 1, 1), date(2026, 1, 5))
    assert history[0]["observed_assignment_count"] == 1


@pytest.mark.parametrize("explicit_group", [None, 2])
@pytest.mark.parametrize("partial", [False, True])
def test_single_direct_membership_does_not_prove_context_assignment_team(explicit_group, partial):
    """Ancestor expansion alone can make one direct membership ambiguous.

    Preserve the known person/time as fixed context; do not silently confirm
    its placement or infer personal approval from the source schedule.
    """
    pytest.importorskip("sp5lib")
    from test_sp5_adapter import SyntheticDatabase
    from sp5generator.sp5_adapter import import_snapshot

    class Source(SyntheticDatabase):
        def get_groups(self):
            return [{"ID": 1}, {"ID": 2, "SUPERID": 1}]

        def get_employee_groups(self, eid):
            return [2]

        def get_group_members(self, gid):
            return [101] if gid == 2 else []

        def get_schedule(self, year, month, group_id=None, **kwargs):
            if (year, month, group_id) != (2026, 1, 2):
                return []
            row = {"employee_id": 101, "date": "2026-01-05", "kind": "shift",
                   "shift_id": 201, "workplace_id": 301}
            if explicit_group is not None:
                row["group_id"] = explicit_group
            return [row]

    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    employee = snapshot.employees[0]
    assert snapshot.metadata["direct_group_memberships"][employee.id] == [2]
    assert employee.team_ids == ["sp5:group:1", "sp5:group:2"]
    assert not employee.approvals
    context = [s for s in snapshot.shifts if s.source == "sp5:existing"]
    assert len(context) == 1
    duty = context[0]
    assert sum((s.end - s.start).total_seconds() / 60 for s in duty.segments) == 240
    assert len(snapshot.assignments) == 1
    assert snapshot.assignments[0].fixed
    provenance = snapshot.metadata["provenance"][duty.id]
    assert provenance["team_confirmed"] is (explicit_group is not None)
    ambiguous = [s for s in snapshot.unresolved if "konkrete Gruppe" in s]
    assert bool(ambiguous) is (explicit_group is None)
    # Even an explicit source team does not confirm duty/approval semantics.
    assert duty.kind == "unconfirmed"
    assert any("Zuordnung zum Besetzungsbedarf und Freigaben" in s for s in snapshot.unresolved)

    from sp5generator.domain import input_diagnostics
    from sp5generator.models import Approval
    from sp5generator.solver import solve
    from sp5generator.validator import validate

    # End-to-end diagnosis: these are imported source records, not handmade
    # demand objects. The raw import fails before CP-SAT model construction.
    result = solve(snapshot, 3, partial=partial)
    assert result.solver_status == "MODEL_INVALID"
    assert {"profile", "unresolved"} <= {d.code for d in result.validation.diagnostics}

    # Deliberately synthetic setup to isolate the remaining historical-date
    # coupling. This is NOT a recipe for clearing real import blockers.
    snapshot.unresolved = []
    snapshot.restrictions = []
    for profile in snapshot.profiles:
        profile.confirmed = True
    for shift in snapshot.shifts:
        shift.kind = "day"
    employee.approvals = [Approval(
        function_id="sp5:service:201", workplace_id="sp5:workplace:301",
        valid_from=snapshot.period_start, valid_until=snapshot.context_end,
    )]
    assert not input_diagnostics(snapshot)
    checked = validate(snapshot, snapshot.assignments)
    boundary_id = snapshot.assignments[0].demand_id
    assert any(d.code == "approval" and d.demand_id == boundary_id for d in checked.diagnostics)
    result = solve(snapshot, 3, partial=partial)
    assert result.solver_status == "INFEASIBLE"
    assert not result.assignments
    assert any(d.code == "fixed_conflict" and d.demand_id == boundary_id
               and "approval" in d.message for d in result.validation.diagnostics)
