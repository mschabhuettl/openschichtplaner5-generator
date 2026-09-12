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


def test_parent_import_includes_children_and_merges_child_team_requirements():
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
    # Both child teams state the same duty: one requirement both may staff.
    shift, = regular
    assert shift.team_id == "sp5:group:2"
    demand, = [d for d in snapshot.demands if d.shift_id == shift.id]
    assert demand.team_ids == ["sp5:group:2", "sp5:group:3"]
    assert not snapshot.assignments
    assert len(snapshot.boundary_work) == 1
    assert len(snapshot.metadata["context_schedule"]) == 1
    assert len(snapshot.restrictions) == 1
    history = historical_matrix(db, snapshot, date(2026, 1, 1), date(2026, 1, 5))
    assert history[0]["observed_assignment_count"] == 1


@pytest.mark.parametrize("explicit_group", [None, 2])
@pytest.mark.parametrize("partial", [False, True])
def test_single_direct_membership_does_not_prove_context_assignment_team(explicit_group, partial):
    """Ancestor expansion alone can make one direct membership ambiguous.

    Preserve the known person/time as personal work; do not silently confirm
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
    context = snapshot.boundary_work
    assert len(context) == 1
    duty = context[0]
    assert sum((s.end - s.start).total_seconds() / 60 for s in duty.segments) == 240
    assert not snapshot.assignments
    provenance = snapshot.metadata["provenance"][duty.id]
    assert provenance["schedule_group_id"] == explicit_group
    assert not hasattr(duty, "team_id")
    assert not any("konkrete Gruppe" in s for s in snapshot.unresolved)
    assert duty.kind == "unknown"
    assert not any("Zuordnung zum Besetzungsbedarf und Freigaben" in s for s in snapshot.unresolved)

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
    assert "boundary_kind" in {d.code for d in input_diagnostics(snapshot)}
    assert solve(snapshot, 3, partial=partial).solver_status == "MODEL_INVALID"
    duty.kind = "day"  # Explicit synthetic setup, not inferred from history.
    assert not input_diagnostics(snapshot)
    assert validate(snapshot, []).valid
    result = solve(snapshot, 3, partial=partial)
    assert result.solver_status == "OPTIMAL"
    assert result.validation.valid
    assert len(result.assignments) == 1
    assert all(a.demand_id in {d.id for d in snapshot.demands} for a in result.assignments)
    assert employee.approvals[0].valid_from == snapshot.period_start


@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("maximum, assigned", [(479, False), (480, True)])
@pytest.mark.parametrize("replacement", [False, True])
def test_imported_boundary_counts_real_weekly_time_without_historical_approval(partial, maximum, assigned, replacement):
    """Real import -> explicit synthetic setup -> solver AND independent validator."""
    pytest.importorskip("sp5lib")
    from test_sp5_adapter import SyntheticDatabase
    from sp5generator.sp5_adapter import import_snapshot
    from sp5generator.models import Approval, Assignment
    from sp5generator.solver import solve
    from sp5generator.validator import validate

    class Source(SyntheticDatabase):
        def get_schedule(self, year, month, **kwargs):
            if (year, month) != (2026, 1):
                return []
            rows = [{"employee_id": 101, "date": "2026-01-05", "kind": "shift",
                     "shift_id": 201, "workplace_id": 301}]
            if replacement:
                rows.append({**rows[0], "kind": "special_shift", "workplace_id": 302,
                             "spshi_type": 0, "startend": "08:00-10:00;11:00-13:00",
                             "duration": 1})
            return rows
        def get_shifts(self, **kwargs):
            # Four hours of real work, one paid hour. No workplace/team on history.
            return [{**s, **{f"DURATION{i}": 1 for i in range(8)}}
                    for s in super().get_shifts(**kwargs)]

    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert not snapshot.assignments
    work, = snapshot.boundary_work
    assert work.kind == "unknown"
    # This deliberately complete synthetic source is confirmed only here.
    # Real audit scripts must not clear missing source/setup prerequisites.
    snapshot.unresolved = []
    snapshot.restrictions = []
    snapshot.context_complete = True
    profile = snapshot.profiles[0]
    profile.confirmed = True
    profile.max_weekly_minutes = maximum
    work.kind = "day"
    for shift in snapshot.shifts:
        shift.kind = "day"
    person = snapshot.employees[0]
    person.approvals = [Approval(function_id="sp5:service:201", workplace_id="sp5:workplace:301",
                                 valid_from=snapshot.period_start, valid_until=snapshot.period_end)]
    proposed = [Assignment(employee_id=person.id, demand_id=snapshot.demands[0].id)]
    checked = validate(snapshot, proposed)
    assert checked.valid is assigned
    assert ("weekly_limit" in {d.code for d in checked.diagnostics}) is (not assigned)
    result = solve(snapshot, 3, partial=partial)
    assert result.solver_status == ("OPTIMAL" if assigned or partial else "INFEASIBLE")
    assert bool(result.assignments) is assigned
    if assigned:
        assert result.validation.valid and result.validation.complete
    elif partial:
        assert result.validation.valid and not result.validation.complete
