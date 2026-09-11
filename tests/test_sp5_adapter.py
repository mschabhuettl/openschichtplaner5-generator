"""New synthetic source structures; no external datasets are loaded."""

from datetime import date
import pytest

pytest.importorskip("sp5lib")
from sp5generator.sp5_adapter import import_snapshot, _local
from zoneinfo import ZoneInfo


class SyntheticDatabase:
    def get_employees(self, **kw):
        return [
            {
                "ID": 101,
                "NAME": "Testperson 001",
                "EMPSTART": "2026-01-01",
                "EMPEND": "2026-12-31",
                "HRSDAY": 8,
                "HRSWEEK": 40,
                "WORKDAYS": "1111100",
            }
        ]

    def get_group_members(self, g):
        return [101]

    def get_employee_groups(self, e):
        return [1]

    def get_holidays(self):
        return [{"DATE": "2026-01-06", "INTERVAL": 0}]

    def get_shifts(self, **kw):
        return [
            {
                "ID": 201,
                "NAME": "Schicht A",
                **{f"STARTEND{i}": "08:00-10:00 11:00-13:00" for i in range(8)},
                **{f"DURATION{i}": 4 for i in range(8)},
            }
        ]

    def get_workplaces(self, **kw):
        return [{"ID": 301, "NAME": "Arbeitsplatz 1"}]

    def get_staffing_requirements(self):
        return {
            "shift_requirements": [
                {
                    "id": 401,
                    "group_id": 1,
                    "weekday": 7,
                    "shift_id": 201,
                    "workplace_id": 301,
                    "min": 1,
                    "max": 2,
                }
            ],
            "daily_requirements": [],
        }

    def get_special_staffing(self, **kw):
        return []

    def get_restrictions(self):
        return [
            {
                "id": 501,
                "employee_id": 101,
                "shift_id": 201,
                "weekday": 7,
                "restrict": 1,
            }
        ]

    def get_schedule(self, year, month, **kw):
        if (year, month) == (2026, 1):
            return [
                {
                    "employee_id": 101,
                    "date": "2026-01-05",
                    "kind": "absence",
                    "interval": 3,
                    "start_time": 600,
                    "end_time": 660,
                }
            ]
        return []


def test_holiday_demand_and_request_restriction():
    s = import_snapshot(
        SyntheticDatabase(), date(2026, 1, 5), date(2026, 1, 6), "1", "UTC"
    )
    assert len(s.demands) == 1
    assert (s.demands[0].minimum, s.demands[0].maximum) == (1, 2)
    assert len(s.shifts[0].segments) == 2 and s.shifts[0].holiday
    assert s.restrictions[0].level == 1 and not s.restrictions[0].approved
    assert not s.employees[0].approvals
    assert s.employees[0].unavailable[0].start.hour == 10
    assert s.unresolved and not s.context_complete


def test_special_and_zero_preserved_not_summed():
    class Source(SyntheticDatabase):
        def get_staffing_requirements(self):
            r = super().get_staffing_requirements()
            r["shift_requirements"][0]["max"] = 0
            r["daily_requirements"] = [
                {"ID": 601, "GROUPID": 1, "START": 0, "START2": 600}
            ]
            return r

        def get_special_staffing(self, **kw):
            return [{"id": 701, "date": "2026-01-06", "min": 3, "max": 4}]

    s = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert not s.demands
    assert len(s.metadata["unresolved_native"]) == 3


@pytest.mark.parametrize("group_field", ["GROUPID", "group_id"])
@pytest.mark.parametrize("group,retained", [(1, True), (99, False), (0, True), (None, True)])
def test_daily_requirement_team_scope_preserves_unresolved_semantics(group_field, group, retained):
    class Source(SyntheticDatabase):
        def get_staffing_requirements(self):
            data = super().get_staffing_requirements()
            data["daily_requirements"] = [{"ID": 601, group_field: group, "START": 600, "MIN": 3}]
            return data

    s = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    rows = s.metadata["unresolved_native"].get("daily_requirements", [])
    assert rows == ([{"ID": 601, group_field: group, "START": 600, "MIN": 3}] if retained else [])
    assert any(message.startswith("DADEM:") for message in s.unresolved) is retained
    # DADEM remains uninterpreted: do not add its MIN to a shift requirement.
    assert len(s.demands) == 1 and s.demands[0].minimum == 1
    assert not s.employees[0].approvals and not s.profiles[0].confirmed


def test_restriction_grades_retained():
    for level in [0, 1, 2]:

        class Source(SyntheticDatabase):
            def get_restrictions(self):
                r = super().get_restrictions()
                r[0]["restrict"] = level
                return r

        s = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
        assert s.restrictions[0].level == level


def test_ambiguous_and_nonexistent_source_clock_blocked():
    for d in [date(2026, 3, 29), date(2026, 10, 25)]:
        with pytest.raises(ValueError):
            _local(d, 150, ZoneInfo("Europe/Berlin"))


def test_existing_context_is_fixed_not_an_absence():
    class Source(SyntheticDatabase):
        def get_schedule(self, year, month, **kw):
            if (year, month) == (2026, 1):
                return [
                    {
                        "employee_id": 101,
                        "date": "2026-01-05",
                        "kind": "shift",
                        "shift_id": 201,
                        "workplace_id": 301,
                    }
                ]
            return []

    s = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert len(s.assignments) == 1 and s.assignments[0].fixed
    assert not s.employees[0].unavailable
    demand = next(d for d in s.demands if d.id == s.assignments[0].demand_id)
    shift = next(v for v in s.shifts if v.id == demand.shift_id)
    assert shift.segments[0].start.date() < s.period_start


def test_service_identity_separates_services_and_preserves_workplaces():
    class Source(SyntheticDatabase):
        def get_shifts(self, **kw):
            shift = super().get_shifts()[0]
            return [shift, {**shift, "ID": 202, "NAME": "Service B"}]

        def get_workplaces(self, **kw):
            return super().get_workplaces() + [{"ID": 302, "NAME": "Workplace B"}]

        def get_staffing_requirements(self):
            row = super().get_staffing_requirements()["shift_requirements"][0]
            return {"shift_requirements": [
                row,
                {**row, "id": 402, "shift_id": 202},
                {**row, "id": 403, "workplace_id": 302},
            ]}

    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    positions = {p.id: p for p in snapshot.positions}
    assert set(positions) == {"sp5:position:201:301", "sp5:position:202:301", "sp5:position:201:302"}
    assert positions["sp5:position:201:301"].function_id == positions["sp5:position:201:302"].function_id == "sp5:service:201"
    assert positions["sp5:position:202:301"].function_id == "sp5:service:202"
    assert positions["sp5:position:202:301"].workplace_id == "sp5:workplace:301"
    assert positions["sp5:position:202:301"].name == "Service B"
    assert len({d.position_id for d in snapshot.demands}) == 3
    assert snapshot.metadata["service_matrix_version"] == 1
    assert snapshot.metadata["workplaces"] == [
        {"id": "sp5:workplace:301", "name": "Arbeitsplatz 1"},
        {"id": "sp5:workplace:302", "name": "Workplace B"},
    ]


def test_explicit_zero_and_unbounded_staffing_without_workplace():
    class Source(SyntheticDatabase):
        def get_staffing_requirements(self):
            row = super().get_staffing_requirements()['shift_requirements'][0]
            return {'shift_requirements': [
                {**row, 'id': 501, 'workplace_id': 0, 'min': 1, 'max': -1},
                {**row, 'id': 502, 'workplace_id': 0, 'min': 0, 'max': 0},
            ]}
    s = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), '1', 'UTC')
    assert [(d.minimum, d.maximum) for d in s.demands] == [(1, None), (0, 0)]
    assert s.positions[0].workplace_id == 'sp5:workplace:0'
    assert any('Importinterpretation bestätigen' in message for message in s.unresolved)
    assert s.metadata['provenance']['sp5:requirement:501']['native_max'] == -1


class ExistingPlanDatabase(SyntheticDatabase):
    def get_schedule(self, year, month, **kw):
        if (year, month) != (2026, 1):
            return []
        return [{"employee_id": 101, "date": "2026-01-06", "kind": "shift",
                 "shift_id": 201, "workplace_id": 301}]


@pytest.mark.parametrize("mode,fixed", [("reference", False), ("fixed", True)])
def test_existing_plan_maps_actual_demand_without_duplicate_staffing(mode, fixed):
    snapshot = import_snapshot(ExistingPlanDatabase(), date(2026, 1, 1), date(2026, 1, 31),
                               "1", "UTC", existing_plan_mode=mode)
    assert len(snapshot.demands) == 1
    assert len(snapshot.assignments) == 1
    assert snapshot.assignments[0].demand_id == snapshot.demands[0].id
    assert snapshot.assignments[0].fixed is fixed
    assert all(d.source == "sp5:SHDEM" for d in snapshot.demands)
    assert snapshot.metadata["reference_schedule"][0]["demand_id"] == snapshot.demands[0].id


def test_default_existing_plan_is_nonfixed_reference():
    snapshot = import_snapshot(ExistingPlanDatabase(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert snapshot.metadata["reference_plan"] == "ist"
    assert not snapshot.assignments[0].fixed
    with pytest.raises(ValueError, match="reference"):
        import_snapshot(ExistingPlanDatabase(), date(2026, 1, 6), date(2026, 1, 6),
                        "1", "UTC", existing_plan_mode="unknown")


@pytest.mark.parametrize("ambiguous", [False, True])
def test_unmatched_or_ambiguous_reference_never_fabricates_demand(ambiguous):
    class Source(ExistingPlanDatabase):
        def get_staffing_requirements(self):
            row = super().get_staffing_requirements()["shift_requirements"][0]
            return {"shift_requirements": [row, {**row, "id": 402}] if ambiguous else []}
    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert not snapshot.assignments
    assert len(snapshot.demands) == (2 if ambiguous else 0)
    reference = snapshot.metadata["unresolved_native"]["reference_schedule"][0]
    assert reference["resolution"] == ("ambiguous" if ambiguous else "unmatched")
    assert reference["shift_id"] == 201


@pytest.mark.parametrize("workplace", [None, 0, 301])
def test_reference_can_match_unbound_demand(workplace):
    class Source(ExistingPlanDatabase):
        def get_staffing_requirements(self):
            result = super().get_staffing_requirements()
            result["shift_requirements"][0]["workplace_id"] = 0
            return result
        def get_schedule(self, year, month, **kw):
            return [{**row, "workplace_id": workplace}
                    for row in super().get_schedule(year, month, **kw)]
    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert len(snapshot.assignments) == 1
    assert len(snapshot.demands) == 1


@pytest.mark.parametrize("explicit_group", [None, 2])
def test_multigroup_reference_requires_unique_group_mapping(explicit_group):
    class Source(ExistingPlanDatabase):
        def get_groups(self):
            return [{"ID": 1}, {"ID": 2}]
        def get_employee_groups(self, e):
            return [1, 2]
        def get_staffing_requirements(self):
            row = super().get_staffing_requirements()["shift_requirements"][0]
            return {"shift_requirements": [row, {**row, "id": 402, "group_id": 2}]}
        def get_schedule(self, year, month, **kw):
            return [{**row, "group_id": explicit_group}
                    for row in super().get_schedule(year, month, **kw)]
    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6),
                               timezone="UTC", team_ids=["1", "2"])
    assert len(snapshot.demands) == 2
    assert len(snapshot.metadata["reference_schedule"]) == 1
    if explicit_group is None:
        assert not snapshot.assignments
        assert snapshot.metadata["reference_schedule"][0]["resolution"] == "ambiguous"
    else:
        assert len(snapshot.assignments) == 1
        demand = next(d for d in snapshot.demands if d.id == snapshot.assignments[0].demand_id)
        shift = next(s for s in snapshot.shifts if s.id == demand.shift_id)
        assert shift.team_id == "sp5:group:2"


@pytest.mark.parametrize("maximum", [0, -1, 3])
def test_date_specific_demand_replaces_holiday_requirement(maximum):
    class Source(SyntheticDatabase):
        def get_special_staffing(self, **kw):
            return [{"id": 701, "date": "2026-01-06", "group_id": 1,
                     "shift_id": 201, "workplace_id": 0, "min": 0, "max": maximum}]
    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert len(snapshot.demands) == 1
    assert snapshot.demands[0].source == "sp5:SPDEM"
    assert snapshot.demands[0].maximum == (None if maximum == -1 else maximum)
    assert snapshot.demands[0].minimum == 0
    snapshot.model_dump_json()


def test_ambiguous_special_demand_never_falls_back_to_regular():
    class Source(SyntheticDatabase):
        def get_special_staffing(self, **kw):
            return [{"id": n, "date": "2026-01-06", "group_id": 1,
                     "shift_id": 201, "workplace_id": 0, "min": 0, "max": n}
                    for n in (1, 2)]
    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert not snapshot.demands
    assert snapshot.metadata["unresolved_native"]["special_requirements"]
    snapshot.model_dump_json()


def test_selected_parent_demand_includes_child_members_without_loading_unselected_people():
    class Source(SyntheticDatabase):
        def get_groups(self):
            return [{"ID": 1, "SUPERID": 0}, {"ID": 2, "SUPERID": 1}]
        def get_group_members(self, group):
            return [101] if group == 2 else []
        def get_employee_groups(self, employee):
            return [2]
    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), team_ids=["1", "2"], timezone="UTC")
    assert snapshot.employees[0].team_ids == ["sp5:group:1", "sp5:group:2"]
    assert snapshot.metadata["direct_group_memberships"]["sp5:employee:101"] == [2]
    assert any("Einsatzbereich bestätigen" in text for text in snapshot.unresolved)
    excluded = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), team_ids=["1"], timezone="UTC")
    assert not excluded.employees


def test_native_time_parser_handles_all_segments_and_rejects_partial_parse():
    from sp5generator.sp5_adapter import _parse_native_windows
    assert _parse_native_windows("06:15-09:45;10:30-14:00") == [(375, 585), (630, 840)]
    assert _parse_native_windows("22:00-24:00") == [(1320, 1440)]
    for value in ("06:15-09:45 garbage", "06:60-09:45", "24:00-25:00"):
        with pytest.raises(ValueError):
            _parse_native_windows(value)


@pytest.mark.parametrize("end", ["13:00", "14:00"])
def test_special_detail_matches_only_identical_nominal_time(end):
    class Source(SyntheticDatabase):
        def get_schedule(self, year, month, **kw):
            if month != 1:
                return []
            return [{"employee_id": 101, "date": "2026-01-06", "kind": "special_shift",
                     "shift_id": 201, "workplace_id": 301, "spshi_type": 0}]
        def get_spshi_entries_for_day(self, date_str, **kw):
            return [{"id": 901, "employee_id": 101, "date": date_str,
                     "shift_id": 201, "workplace_id": 301, "type": 0,
                     "startend": f"08:00-10:00;11:00-{end}", "duration": 4}]
    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert bool(snapshot.assignments) == (end == "13:00")
    assert snapshot.metadata["context_schedule"][0]["startend"]
    assert any(text.startswith("Sonderdienst") for text in snapshot.unresolved) == (end != "13:00")


def test_unused_native_time_slot_is_not_imported_as_a_full_day():
    class Source(SyntheticDatabase):
        def get_shifts(self, **kw):
            return [{**shift, "STARTEND7": "08:00-12:00 00:00-00:00"}
                    for shift in super().get_shifts(**kw)]
    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert len(snapshot.shifts[0].segments) == 1
    assert snapshot.shifts[0].segments[0].start.hour == 8
    assert snapshot.shifts[0].segments[0].end.hour == 12


@pytest.mark.parametrize("start,end", [(-1, 60), (1500, 1600), (None, 60), (30, 1441), (10.5, 60)])
def test_invalid_native_absence_does_not_change_day_or_truncate_minutes(start, end):
    class Source(SyntheticDatabase):
        def get_schedule(self, year, month, **kw):
            return [{**row, "start_time": start, "end_time": end}
                    for row in super().get_schedule(year, month, **kw)]
    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert not snapshot.employees[0].unavailable
    assert any("ungültiges Intervall" in issue for issue in snapshot.unresolved)


def test_context_records_for_different_workplaces_have_distinct_ids():
    class Source(SyntheticDatabase):
        def get_schedule(self, year, month, **kw):
            if (year, month) != (2026, 1):
                return []
            return [{"employee_id": 101, "date": "2026-01-05", "kind": "shift",
                     "shift_id": 201, "workplace_id": workplace}
                    for workplace in (0, 301, 302)]
    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert len(snapshot.assignments) == 3
    assert len({assignment.demand_id for assignment in snapshot.assignments}) == 3
    assert len({demand.id for demand in snapshot.demands}) == len(snapshot.demands)
    context_positions = [p for p in snapshot.positions if p.id.startswith("sp5:context-position:")]
    assert {p.workplace_id for p in context_positions} == {
        "sp5:workplace:0", "sp5:workplace:301", "sp5:workplace:302"}


def test_context_uses_explicit_group_for_multi_group_member():
    class Source(SyntheticDatabase):
        def get_groups(self):
            return [{"ID": 1}, {"ID": 2}]
        def get_employee_groups(self, employee):
            return [1, 2]
        def get_schedule(self, year, month, **kw):
            if (year, month) != (2026, 1):
                return []
            return [{"employee_id": 101, "date": "2026-01-05", "kind": "shift",
                     "shift_id": 201, "workplace_id": 301, "group_id": 2}]
    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), timezone="UTC", team_ids=["1", "2"])
    context = next(shift for shift in snapshot.shifts if shift.source == "sp5:existing")
    assert context.team_id == "sp5:group:2"
    assert snapshot.metadata["provenance"][context.id]["team_confirmed"] is True


def test_identical_context_nominal_and_special_entries_count_once():
    class Source(SyntheticDatabase):
        def get_schedule(self, year, month, **kw):
            if (year, month) != (2026, 1):
                return []
            return [{"employee_id": 101, "date": "2026-01-05", "kind": kind,
                     "shift_id": 201, "workplace_id": 301, "spshi_type": 0,
                     "startend": "08:00-10:00 11:00-13:00", "duration": 4}
                    for kind in ("shift", "special_shift")]
    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert len(snapshot.assignments) == 1
    assert len([demand for demand in snapshot.demands if demand.source == "sp5:existing"]) == 1


@pytest.mark.parametrize("value", ["NaN", "Infinity", "not-a-number"])
def test_invalid_native_duration_is_a_controlled_import_error(value):
    from sp5generator.sp5_adapter import _minutes
    with pytest.raises(ValueError, match="Stundenangabe"):
        _minutes(value)


@pytest.mark.parametrize("entrypoint", ["snapshot", "directory", "api"])
@pytest.mark.parametrize("days", [-1, 366])
def test_import_period_limits_are_checked_before_source_access(entrypoint, days):
    from datetime import timedelta
    from sp5generator.sp5_adapter import import_directory
    from sp5generator.api_adapter import import_api
    start = date(2026, 1, 1)
    end = start + timedelta(days=days)
    with pytest.raises(ValueError, match="1 bis 366 Kalendertage"):
        if entrypoint == "snapshot":
            import_snapshot(None, start, end, "1", "UTC")
        elif entrypoint == "directory":
            import_directory("source-must-not-be-opened", start, end, "1", "UTC")
        else:
            import_api(start, end, "1", "UTC")


def test_requirement_ids_are_scoped_to_the_native_cell():
    class Source(SyntheticDatabase):
        def get_shifts(self, **kwargs):
            first = super().get_shifts(**kwargs)[0]
            return [first, {**first, "ID": 202, "NAME": "Schicht B"}]
        def get_staffing_requirements(self):
            source = super().get_staffing_requirements()
            first = source["shift_requirements"][0]
            source["shift_requirements"] = [first, dict(first), {**first, "shift_id": 202}]
            return source
    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert len(snapshot.demands) == 2
    assert len({d.id for d in snapshot.demands}) == 2


def test_history_distinct_days_and_deviations_do_not_inflate_evidence():
    from sp5generator.sp5_adapter import historical_matrix
    class Source(SyntheticDatabase):
        def get_schedule(self, year, month, **kw):
            return [
                {'employee_id': 101, 'date': '2026-01-02', 'kind': 'shift', 'shift_id': 201, 'workplace_id': wid}
                for wid in (0, 301)
            ] + [{'employee_id': 101, 'date': '2026-01-03', 'kind': 'special_shift',
                  'shift_id': 201, 'workplace_id': 301, 'spshi_type': 1}]
    db = Source()
    snapshot = import_snapshot(db, date(2026, 1, 6), date(2026, 1, 6), '1', 'UTC')
    history = historical_matrix(db, snapshot, date(2026, 1, 1), date(2026, 1, 5))
    evidence = history[0]['suggested_approvals'][0]
    assert evidence['evidence_count'] == 2
    assert evidence['evidence_days'] == 1


def test_import_uses_personal_approval_without_implicit_qualification_gate():
    from sp5generator.domain import eligibility
    from sp5generator.models import Approval

    class Source(SyntheticDatabase):
        def get_restrictions(self):
            return []

        def get_schedule(self, *args, **kwargs):
            return []

    s = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    employee, demand = s.employees[0], s.demands[0]
    s.shifts[0].kind = "day"
    assert "approval" in eligibility(s, employee, demand)
    employee.approvals.append(Approval(
        function_id=s.positions[0].function_id, workplace_id="*",
        valid_from=s.period_start, valid_until=s.period_end,
    ))
    assert eligibility(s, employee, demand) == []
    s.positions[0].qualifications_required = True
    assert "qualification" in eligibility(s, employee, demand)


@pytest.mark.parametrize(
    "basis,start,end,expected_hours",
    [
        (0, "2026-02-02", "2026-02-08", 35),
        (1, "2026-02-02", "2026-02-08", 36),
        (2, "2026-02-01", "2026-02-28", 156),
        (2, "2026-02-02", "2026-02-08", 35),
        (2, "2026-02-01", "2026-03-31", 312),
        (3, "2026-01-01", "2026-12-31", 1800),
    ],
)
def test_nominal_hours_respect_source_basis_and_selected_period(basis, start, end, expected_hours):
    class NominalDatabase(SyntheticDatabase):
        def get_employees(self, **kw):
            return [{**super().get_employees(**kw)[0], "CALCBASE": basis,
                     "HRSDAY": 7, "HRSWEEK": 36, "HRSMONTH": 156, "HRSTOTAL": 1800}]

    snapshot = import_snapshot(NominalDatabase(), date.fromisoformat(start), date.fromisoformat(end), "1", "UTC")
    person = snapshot.employees[0]
    assert person.target_minutes == expected_hours * 60
    origin = snapshot.metadata["provenance"][person.id]["nominal_hours"]
    assert origin == {
        "calcbase": basis, "hours_day": 7.0, "hours_week": 36.0,
        "hours_month": 156.0, "hours_total": 1800.0,
        "period_start": start, "period_end": end,
        "target_minutes": expected_hours * 60, "bookings_included": False,
    }
    assert any("Sollbuchungen" in item for item in snapshot.unresolved)


def test_reference_source_is_explicit_ist_independent_of_library_default():
    class Source(ExistingPlanDatabase):
        def get_schedule(self, year, month, *, plan, **kw):
            assert plan == "ist"
            return super().get_schedule(year, month, **kw)

    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert snapshot.metadata["reference_plan"] == "ist"
    assert len(snapshot.assignments) == 1
    assert not snapshot.employees[0].approvals
    assert snapshot.unresolved


@pytest.mark.parametrize('plan,service', [('ist', 201), ('soll', 202)])
@pytest.mark.parametrize('mode,fixed', [('reference', False), ('fixed', True)])
def test_reference_selection_never_switches_context_absences_or_special_duties(plan, service, mode, fixed):
    class Source(SyntheticDatabase):
        calls = []

        def get_shifts(self, **kw):
            original = super().get_shifts()[0]
            return [original, {**original, 'ID': 202, 'NAME': 'Soll-Dienst'}]

        def get_staffing_requirements(self):
            original = super().get_staffing_requirements()['shift_requirements'][0]
            return {'shift_requirements': [original, {**original, 'id': 402, 'shift_id': 202}], 'daily_requirements': []}

        def get_schedule(self, year, month, *, plan, **kw):
            self.calls.append((year, month, plan))
            if (year, month) != (2026, 1):
                return []
            sid = 201 if plan == 'ist' else 202
            return [
                *[{'employee_id': 101, 'date': f'2026-01-{day:02}', 'kind': 'shift', 'shift_id': sid, 'workplace_id': 301} for day in (5, 6, 7)],
                {'employee_id': 101, 'date': '2026-01-06', 'kind': 'absence', 'interval': 3,
                 'start_time': 480 if plan == 'ist' else 720, 'end_time': 540 if plan == 'ist' else 780},
                {'employee_id': 101, 'date': '2026-01-06', 'kind': 'special_shift', 'shift_id': 201,
                 'spshi_type': 1, 'duration': 1 if plan == 'ist' else 2},
            ]

    source = Source()
    snapshot = import_snapshot(source, date(2026, 1, 6), date(2026, 1, 6), '1', 'UTC',
                               reference_plan=plan, existing_plan_mode=mode)
    assert snapshot.metadata['reference_plan'] == plan
    assert snapshot.metadata['context_plan'] == snapshot.metadata['availability_plan'] == snapshot.metadata['special_shift_plan'] == 'ist'
    references = snapshot.metadata['reference_schedule']
    assert len(references) == 1 and references[0]['shift_id'] == service
    reference = next(a for a in snapshot.assignments if a.demand_id == references[0]['demand_id'])
    assert reference.fixed is fixed
    context = [r for r in snapshot.metadata['context_schedule'] if r['date'] != '2026-01-06']
    assert len(context) == 2 and all(r['shift_id'] == 201 for r in context)
    assert all(a.fixed for a in snapshot.assignments if a != reference)
    assert snapshot.employees[0].unavailable[0].start.hour == 8
    special = next(r for r in snapshot.metadata['context_schedule'] if r['kind'] == 'special_shift')
    assert special['duration'] == 1
    assert sum(d.source == 'sp5:SHDEM' for d in snapshot.demands) == 2
    assert not snapshot.employees[0].approvals and not snapshot.context_complete
    assert all(not p.confirmed for p in snapshot.profiles)
    assert any('Sonderdienst' in message for message in snapshot.unresolved)
    assert all((year, month) == (2026, 1) for year, month, selected in source.calls if selected == 'soll')


def test_empty_soll_reference_does_not_fall_back_to_ist_or_accept_both():
    class Source(ExistingPlanDatabase):
        def get_schedule(self, year, month, *, plan, **kw):
            return [] if plan == 'soll' else super().get_schedule(year, month, **kw)

    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), '1', 'UTC', reference_plan='soll')
    assert snapshot.metadata['reference_schedule'] == []
    assert snapshot.assignments == []
    assert len(snapshot.demands) == 1
    with pytest.raises(ValueError, match='Referenzplansicht'):
        import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), '1', 'UTC', reference_plan='both')


@pytest.mark.parametrize('reason', ['missing_demand', 'team_mismatch', 'workplace_mismatch', 'zero_capacity', 'ambiguous'])
def test_reference_reason_explains_first_failed_filter_without_creating_demand(reason):
    class Source(ExistingPlanDatabase):
        def get_staffing_requirements(self):
            row = super().get_staffing_requirements()['shift_requirements'][0]
            if reason == 'missing_demand':
                return {'shift_requirements': []}
            if reason == 'zero_capacity':
                row = {**row, 'min': 0, 'max': 0}
            return {'shift_requirements': [row, {**row, 'id': 402}] if reason == 'ambiguous' else [row]}

        def get_schedule(self, year, month, **kw):
            return [{**row, **({'group_id': 2} if reason == 'team_mismatch' else {}),
                     **({'workplace_id': 999} if reason == 'workplace_mismatch' else {})}
                    for row in super().get_schedule(year, month, **kw)]

    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), '1', 'UTC')
    reference = snapshot.metadata['reference_schedule'][0]
    assert reference['resolution_reason'] == reason
    assert reference['resolution'] == ('ambiguous' if reason == 'ambiguous' else 'unmatched')
    assert len(reference['candidate_demand_ids']) == (2 if reason == 'ambiguous' else 0)
    assert not snapshot.assignments and not snapshot.employees[0].approvals
    assert snapshot.metadata['unresolved_native']['reference_schedule'][0] == reference
    assert len(snapshot.demands) == (0 if reason == 'missing_demand' else 2 if reason == 'ambiguous' else 1)


def test_new_import_proposes_authorized_rest_defaults_without_confirming_setup():
    from sp5generator.domain import input_diagnostics
    s = import_snapshot(SyntheticDatabase(), date(2026, 1, 5), date(2026, 1, 6), '1', 'UTC')
    p = s.profiles[0]
    assert (p.min_rest_minutes, p.weekly_rest_minutes) == (660, 2160)
    assert p.weekly_rest_frame == 'calendar_week'
    assert p.weekly_rest_add_daily is False
    assert not p.confirmed and p.source == 'unresolved'
    assert p.max_consecutive_work_days is None
    assert all(not e.approvals for e in s.employees)
    assert s.objectives.workday_transitions == 100
    assert input_diagnostics(s)  # Proposed values do not remove setup blockers.
