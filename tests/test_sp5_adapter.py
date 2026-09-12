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


@pytest.mark.parametrize(
    "employment_periods,expected_count",
    [
        ([("2026-01-01", "2026-01-04")], 1),
        ([("2026-01-07", "2026-12-31")], 1),
        ([("2026-01-01", "2026-01-04"), ("2026-01-07", "2026-12-31")], 2),
        ([("2026-01-01", "2026-12-31")], 0),
        ([("2026-01-01", "2026-01-05")], 0),
        ([("2026-01-06", "2026-12-31")], 0),
    ],
)
def test_not_employed_in_period_is_reported_once_without_dropping_people(
    employment_periods, expected_count
):
    class Source(SyntheticDatabase):
        def get_employees(self, **kw):
            employee = super().get_employees(**kw)[0]
            return [
                {**employee, "ID": 101 + index, "EMPSTART": start, "EMPEND": end}
                for index, (start, end) in enumerate(employment_periods)
            ]

        def get_group_members(self, g):
            return [101 + index for index in range(len(employment_periods))]

    snapshot = import_snapshot(Source(), date(2026, 1, 5), date(2026, 1, 6), "1", "UTC")

    assert {person.id for person in snapshot.employees} == {
        f"sp5:employee:{101 + index}" for index in range(len(employment_periods))
    }
    assert snapshot.metadata["not_employed_in_period"] == expected_count
    messages = [
        message for message in snapshot.unresolved
        if "im Planungszeitraum nicht beschäftigt" in message
    ]
    assert len(messages) == (1 if expected_count else 0)
    if expected_count:
        assert messages[0].startswith(f"{expected_count} der importierten Personen")
        assert "früheren Dienstkontexts erhalten" in messages[0]
        assert "keinen Bedarf decken" in messages[0]
        assert all(person.name not in messages[0] for person in snapshot.employees)


def test_native_24_hour_window_paid_duration_and_nominal_week_are_distinct():
    from sp5generator.timeutils import day_minutes

    class Source(SyntheticDatabase):
        def get_shifts(self, **kw):
            rows = super().get_shifts(**kw)
            rows[0].update(STARTEND7="08:00-08:00", DURATION7=8)
            return rows

        def get_employees(self, **kw):
            rows = super().get_employees(**kw)
            rows[0].update(CALCBASE=1, HRSWEEK=40)
            return rows

    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "Europe/Vienna")
    duty = snapshot.shifts[0]
    assert day_minutes(duty, snapshot.timezone) == {date(2026, 1, 6): 960, date(2026, 1, 7): 480}
    assert duty.paid_minutes == 480
    # HRSWEEK informs CALCBASE nominal hours, never an invented hard maximum.
    assert snapshot.profiles[0].max_daily_minutes is None
    assert snapshot.profiles[0].max_weekly_minutes is None
    assert snapshot.profiles[0].min_rest_minutes == 660
    assert snapshot.profiles[0].weekly_rest_minutes == 2160
    assert not snapshot.profiles[0].confirmed and not snapshot.employees[0].approvals


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


@pytest.mark.parametrize("group_field", ["GROUPID", "group_id"])
@pytest.mark.parametrize("group", [True, False, 1.5, "99", [], {}, float("inf")])
def test_invalid_daily_team_cannot_silently_remove_unresolved_requirement(group_field, group):
    row = {"ID": 601, group_field: group, "START": 600, "MIN": 3}

    class Source(SyntheticDatabase):
        def get_staffing_requirements(self):
            data = super().get_staffing_requirements()
            data["daily_requirements"] = [row]
            return data

    s = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert s.metadata["unresolved_native"]["daily_requirements"] == [row]
    assert any("DADEM: Ungültige Kennung" in message for message in s.unresolved)
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


def test_existing_context_is_personal_work_not_staffing_or_absence():
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
    assert not s.assignments
    assert not s.employees[0].unavailable
    work, = s.boundary_work
    assert work.segments[0].start.date() < s.period_start
    assert work.employee_id == s.employees[0].id
    assert work.kind == "unknown"
    assert not any(d.source == "sp5:existing" for d in s.demands)
    assert not s.employees[0].approvals
    assert not any("Besetzungsbedarf und Freigaben" in issue for issue in s.unresolved)


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


def test_requirements_demand_source_matches_the_default():
    default = import_snapshot(
        ExistingPlanDatabase(), date(2026, 1, 5), date(2026, 1, 6), "1", "UTC"
    )
    explicit = import_snapshot(
        ExistingPlanDatabase(), date(2026, 1, 5), date(2026, 1, 6), "1", "UTC",
        demand_source="requirements",
    )
    assert explicit.model_dump(exclude={"created_at"}) == default.model_dump(exclude={"created_at"})
    assert default.metadata["demand_source"] == "requirements"
    assert "observed_demand" not in default.metadata


@pytest.mark.parametrize("demand_source", ["unknown", "", "Observed", None, 1])
def test_invalid_demand_source_is_rejected(demand_source):
    with pytest.raises(ValueError, match="requirements.*observed"):
        import_snapshot(
            SyntheticDatabase(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC",
            demand_source=demand_source,
        )


@pytest.mark.parametrize("days", [["2026-01-06"], ["2026-01-05", "2026-01-06"]])
def test_observed_demand_counts_distinct_people_per_day_and_uses_catalog_times(days):
    class Source(ExistingPlanDatabase):
        def get_employees(self, **kw):
            employee = super().get_employees(**kw)[0]
            return [employee, {**employee, "ID": 102, "NAME": "Testperson 002"}]

        def get_group_members(self, g):
            return [101, 102]

        def get_shifts(self, **kw):
            return [{**row, "STARTEND7": "06:00-09:00 10:00-12:00", "DURATION7": 4.5}
                    for row in super().get_shifts(**kw)]

        def get_staffing_requirements(self):
            data = super().get_staffing_requirements()
            data["shift_requirements"][0].update(min=9, max=10)
            return data

        def get_schedule(self, year, month, **kw):
            rows = super().get_schedule(year, month, **kw)
            if not rows:
                return []
            return [
                {**rows[0], "date": day, "employee_id": employee, "group_id": group}
                for day in days for employee, group in [(101, None), (101, 1), (102, 1)]
            ]

    baseline = import_snapshot(Source(), date(2026, 1, 5), date(2026, 1, 7), "1", "UTC")
    snapshot = import_snapshot(
        Source(), date(2026, 1, 5), date(2026, 1, 7), "1", "UTC", demand_source="observed"
    )
    assert len(snapshot.demands) == len(days)
    assert len({demand.id for demand in snapshot.demands}) == len(days)
    assert {demand.shift_id for demand in snapshot.demands} == {
        f"sp5:shift:201:{day}" for day in days
    }
    for demand in snapshot.demands:
        assert (demand.minimum, demand.maximum) == (2, 2)
        assert demand.position_id == "sp5:position:201:301"
        assert demand.team_ids == ["sp5:group:1"]
    position, = snapshot.positions
    assert position.function_id == "sp5:service:201"
    assert position.workplace_id == "sp5:workplace:301"
    assert not position.qualifications_required
    for shift in snapshot.shifts:
        holiday = shift.segments[0].start.date() == date(2026, 1, 6)
        assert shift.holiday is holiday
        assert [(segment.start.hour, segment.end.hour) for segment in shift.segments] == (
            [(6, 9), (10, 12)] if holiday else [(8, 10), (11, 13)]
        )
        assert shift.paid_minutes == (270 if holiday else 240)
    assert snapshot.metadata["demand_source"] == "observed"
    assert snapshot.metadata["observed_demand"] == {
        "cells": len(days), "slots": 2 * len(days), "skipped": 0,
    }
    messages = [message for message in snapshot.unresolved if message not in baseline.unresolved]
    assert len(messages) == 1
    message = messages[0].lower()
    assert all(word in message for word in (
        "beobachtet", "zeitraum", "abgeleitet", "bedarfstabelle", "quelle",
        "dienst", "arbeitsplatz", "tag", "unter-", "obergrenze", "prüfen",
    ))
    assert all(person.name not in messages[0] for person in snapshot.employees)
    assert snapshot.employees == baseline.employees
    assert snapshot.profiles == baseline.profiles
    assert snapshot.boundary_work == baseline.boundary_work
    assert len(snapshot.assignments) == 2 * len(days)
    assert not any(assignment.fixed for assignment in snapshot.assignments)


@pytest.mark.parametrize(
    "row_groups,person_groups,expected_groups",
    [([1, 2], [1, 2, 99], [1, 2]), ([2, 99], [1, 99], [2]),
     ([None, 99], [1, 99], [1]), ([None, 99], [99], [])],
)
def test_observed_demand_uses_selected_row_groups_then_person_groups(
    row_groups, person_groups, expected_groups
):
    class Source(ExistingPlanDatabase):
        def get_groups(self):
            return [{"ID": group} for group in (1, 2, 99)]

        def get_employee_groups(self, e):
            return person_groups

        def get_schedule(self, year, month, **kw):
            return [{**row, "group_id": group}
                    for row in super().get_schedule(year, month, **kw) for group in row_groups]

    snapshot = import_snapshot(
        Source(), date(2026, 1, 6), date(2026, 1, 6), timezone="UTC",
        team_ids=["1", "2"], demand_source="observed",
    )
    assert snapshot.metadata["observed_demand"] == {
        "cells": int(bool(expected_groups)), "slots": int(bool(expected_groups)),
        "skipped": int(not expected_groups),
    }
    if expected_groups:
        demand, = snapshot.demands
        assert demand.team_ids == [f"sp5:group:{group}" for group in expected_groups]
        assert (demand.minimum, demand.maximum) == (1, 1)
    else:
        assert not snapshot.demands


def test_observed_references_match_their_exact_workplace_cell():
    class Source(ExistingPlanDatabase):
        def get_employees(self, **kw):
            employee = super().get_employees(**kw)[0]
            return [employee, {**employee, "ID": 102, "NAME": "Testperson 002"}]

        def get_group_members(self, g):
            return [101, 102]

        def get_schedule(self, year, month, **kw):
            return [{**row, "employee_id": employee, "workplace_id": workplace}
                    for row in super().get_schedule(year, month, **kw)
                    for employee, workplace in [(101, 0), (102, 301)]]

    snapshot = import_snapshot(
        Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC", demand_source="observed"
    )
    demands = {demand.position_id: demand for demand in snapshot.demands}
    assert set(demands) == {"sp5:position:201:0", "sp5:position:201:301"}
    assert all((demand.minimum, demand.maximum) == (1, 1) for demand in demands.values())
    references = snapshot.metadata["reference_schedule"]
    assert len(references) == 2
    for reference in references:
        demand = demands[f"sp5:position:201:{reference['workplace_id']}"]
        assert reference["candidate_demand_ids"] == [demand.id]
        assert reference["demand_id"] == demand.id
        assert "resolution" not in reference
    assert {(assignment.employee_id, assignment.demand_id) for assignment in snapshot.assignments} == {
        ("sp5:employee:101", demands["sp5:position:201:0"].id),
        ("sp5:employee:102", demands["sp5:position:201:301"].id),
    }


def test_observed_reference_maps_using_person_team_when_row_group_is_outside_selection():
    class Source(ExistingPlanDatabase):
        def get_schedule(self, year, month, **kw):
            return [{**row, "group_id": 99}
                    for row in super().get_schedule(year, month, **kw)]

    snapshot = import_snapshot(
        Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC", demand_source="observed"
    )
    demand, = snapshot.demands
    assert demand.team_ids == snapshot.employees[0].team_ids == ["sp5:group:1"]
    reference, = snapshot.metadata["reference_schedule"]
    assert reference["group_id"] == 99
    assert reference["candidate_demand_ids"] == [demand.id]
    assert reference["demand_id"] == demand.id
    assert "resolution" not in reference
    assignment, = snapshot.assignments
    assert assignment.employee_id == "sp5:employee:101"
    assert assignment.demand_id == demand.id


@pytest.mark.parametrize("plan,expected_day", [("ist", "2026-01-06"), ("soll", "2026-01-07")])
def test_observed_demand_uses_the_selected_reference_plan(plan, expected_day):
    class Source(ExistingPlanDatabase):
        def get_schedule(self, year, month, *, plan, **kw):
            return [{**row, "date": "2026-01-06" if plan == "ist" else "2026-01-07"}
                    for row in super().get_schedule(year, month, **kw)]

    snapshot = import_snapshot(
        Source(), date(2026, 1, 6), date(2026, 1, 7), "1", "UTC",
        reference_plan=plan, demand_source="observed",
    )
    demand, = snapshot.demands
    assert demand.shift_id == f"sp5:shift:201:{expected_day}"
    assert snapshot.metadata["reference_schedule"][0]["demand_id"] == demand.id


@pytest.mark.parametrize("plan,cells", [("ist", 0), ("soll", 1)])
def test_observed_demand_preserves_special_replacement_and_personal_work(plan, cells):
    class Source(ExistingPlanDatabase):
        def get_schedule(self, year, month, **kw):
            rows = super().get_schedule(year, month, **kw)
            return rows + [{**row, "kind": "special_shift", "spshi_type": 0,
                            "startend": "09:00-11:00", "duration": 2} for row in rows]

    baseline = import_snapshot(
        Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC", reference_plan=plan
    )
    snapshot = import_snapshot(
        Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC",
        reference_plan=plan, demand_source="observed",
    )
    assert snapshot.metadata["observed_demand"] == {"cells": cells, "slots": cells, "skipped": 0}
    assert len(snapshot.demands) == cells
    assert snapshot.boundary_work == baseline.boundary_work
    assert snapshot.metadata["personal_period_work"] == baseline.metadata["personal_period_work"] == 1
    assert snapshot.metadata["context_schedule"] == baseline.metadata["context_schedule"]


def test_observed_demand_does_not_invent_cells_without_reference_duties():
    class Source(ExistingPlanDatabase):
        def get_schedule(self, year, month, **kw):
            return [
                changed for row in super().get_schedule(year, month, **kw)
                for changed in [row | {"date": "2026-01-05"}, row | {"shift_id": 999},
                                row | {"kind": "absence", "interval": 0}]
            ]

    baseline = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    snapshot = import_snapshot(
        Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC", demand_source="observed"
    )
    assert not snapshot.demands
    assert snapshot.metadata["observed_demand"] == {"cells": 0, "slots": 0, "skipped": 0}
    assert snapshot.employees == baseline.employees
    assert snapshot.boundary_work == baseline.boundary_work
    assert len([message for message in snapshot.unresolved if "abgeleitet" in message]) == 1


@pytest.mark.parametrize(
    "reference_services,services,slots",
    [([201, 202], 0, 0), ([204], 2, 6), ([202], 1, 3), ([], 0, 0)],
    ids=["matching", "missing", "partly_matching", "empty"],
)
def test_demanded_without_reference_counts_services_and_required_slots(
    reference_services, services, slots
):
    class Source(SyntheticDatabase):
        def get_shifts(self, **kw):
            shift = super().get_shifts()[0]
            return [{**shift, "ID": service, "NAME": f"Testdienst {service}"}
                    for service in (201, 202, 203, 204)]

        def get_workplaces(self, **kw):
            return super().get_workplaces() + [{"ID": 302, "NAME": "Arbeitsplatz 2"}]

        def get_staffing_requirements(self):
            row = super().get_staffing_requirements()["shift_requirements"][0]
            return {"shift_requirements": [
                row,
                {**row, "id": 402, "workplace_id": 302, "min": 2},
                {**row, "id": 403, "shift_id": 202, "min": 3, "max": 3},
                {**row, "id": 404, "shift_id": 203, "min": 0, "max": 4},
            ]}

        def get_schedule(self, year, month, **kw):
            if (year, month) != (2026, 1):
                return []
            return [{"employee_id": 101, "date": "2026-01-06", "kind": "shift",
                     "shift_id": service, "workplace_id": 301}
                    for service in reference_services]

    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert [row["shift_id"] for row in snapshot.metadata["reference_schedule"]] == reference_services
    assert snapshot.metadata["demanded_without_reference"] == {"services": services, "slots": slots}
    messages = [message for message in snapshot.unresolved if "geforderte Dienstarten" in message]
    assert len(messages) == (1 if services else 0)
    if services:
        assert messages[0].startswith(
            f"{services} geforderte Dienstarten mit {slots} Pflichtplätzen "
            "kommen im Vergleichsplan des Zeitraums nicht vor."
        )
        assert "Testdienst" not in messages[0] and "Testperson" not in messages[0]
    assert sorted((d.minimum, d.maximum) for d in snapshot.demands) == [(0, 4), (1, 2), (2, 2), (3, 3)]
    assert not snapshot.employees[0].approvals


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
def test_multigroup_requirement_merges_into_one_staffable_demand(explicit_group):
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
    # Both groups state the same duty at the same workplace and day: one
    # requirement, staffable from either group, so the existing duty maps
    # without an ambiguous group choice whether or not the source names one.
    demand, = snapshot.demands
    assert (demand.minimum, demand.maximum) == (1, 2)
    assert demand.team_ids == ["sp5:group:1", "sp5:group:2"]
    assert len(snapshot.metadata["reference_schedule"]) == 1
    reference, = snapshot.metadata["reference_schedule"]
    assert "resolution" not in reference and reference["demand_id"] == demand.id
    assignment, = snapshot.assignments
    assert assignment.demand_id == demand.id
    assert [entry["group_id"] for entry
            in snapshot.metadata["provenance"][demand.id]["merged_requirements"]] == [1, 2]


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
    # Only identical nominal time covers the demand; anything else is personal
    # work with the source's own times, never a silently dropped duty.
    assert bool(snapshot.boundary_work) == (end != "13:00")
    assert snapshot.metadata["personal_period_work"] == (0 if end == "13:00" else 1)
    assert not any(text.startswith("Sonderdienst") for text in snapshot.unresolved)


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
    assert not snapshot.assignments
    assert len(snapshot.boundary_work) == 3
    assert len({work.id for work in snapshot.boundary_work}) == 3
    assert {snapshot.metadata["provenance"][w.id]["workplace_id"] for w in snapshot.boundary_work} == {0, 301, 302}
    assert not any(p.id.startswith("sp5:context-position:") for p in snapshot.positions)


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
    context, = snapshot.boundary_work
    assert snapshot.metadata["provenance"][context.id]["schedule_group_id"] == 2
    assert not hasattr(context, "team_id")
    assert not any("konkrete Gruppe" in issue for issue in snapshot.unresolved)


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
    assert not snapshot.assignments
    assert len(snapshot.boundary_work) == 1
    assert not any(demand.source == "sp5:existing" for demand in snapshot.demands)


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
    if plan == 'ist':
        # Unknown replacement times block; the replaced normal duty is not
        # a valid fallback reference (nor an implicitly confirmed absence).
        assert references == []
        assert snapshot.assignments == []
    else:
        assert len(references) == 1 and references[0]['shift_id'] == service
        reference = next(a for a in snapshot.assignments if a.demand_id == references[0]['demand_id'])
        assert reference.fixed is fixed
        assert snapshot.assignments == [reference]
    context = [r for r in snapshot.metadata['context_schedule'] if r['date'] != '2026-01-06']
    assert len(context) == 2 and all(r['shift_id'] == 201 for r in context)
    assert len(snapshot.boundary_work) == 2
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


@pytest.mark.parametrize("plan", ["ist", "soll"])
def test_absence_type_provenance_survives_deduplication_and_json(plan):
    import json

    class Source(SyntheticDatabase):
        def get_schedule(self, year, month, **kw):
            rows = super().get_schedule(year, month, **kw)
            if not rows:
                return []
            row = rows[0]
            # Same interval, different accounting types; repeated team rows
            # must still deduplicate, while distinct types must not collapse.
            return [{**row, "leave_type_id": kind, "note": "not for export"}
                    for kind in (701, 702, 701, None)]

    snapshot = import_snapshot(Source(), date(2026, 1, 5), date(2026, 1, 6),
                               "1", "UTC", reference_plan=plan)
    data = json.loads(snapshot.model_dump_json())
    rows = data["metadata"]["context_schedule"]
    assert [r["leave_type_id"] for r in rows] == [701, 702, None]
    assert all("note" not in r for r in rows)
    # Provenance is not a credit, an approval or a confirmation.
    baseline = import_snapshot(SyntheticDatabase(), date(2026, 1, 5),
                               date(2026, 1, 6), "1", "UTC", reference_plan=plan)
    assert snapshot.profiles == baseline.profiles
    assert snapshot.employees[0].model_dump(exclude={"unavailable"}) == baseline.employees[0].model_dump(exclude={"unavailable"})
    assert set((i.start, i.end) for i in snapshot.employees[0].unavailable) == set((i.start, i.end) for i in baseline.employees[0].unavailable)
    assert not snapshot.employees[0].approvals


@pytest.mark.parametrize("special", [False, True])
@pytest.mark.parametrize("field,value", [
    ("min", -1), ("min", -1.0),
    ("min", float("nan")), ("max", float("nan")),
    ("min", float("inf")), ("max", float("inf")),
    ("min", float("-inf")), ("max", float("-inf")),
])
def test_direct_library_invalid_counts_do_not_reach_shift_builder(special, field, value):
    class InvalidCounts(SyntheticDatabase):
        def get_staffing_requirements(self):
            result = super().get_staffing_requirements()
            if not special:
                result["shift_requirements"][0][field] = value
            return result

        def get_special_staffing(self, **kw):
            if not special:
                return []
            row = super().get_staffing_requirements()["shift_requirements"][0]
            return [{**row, "date": "2026-01-06", field: value}]

    snapshot = import_snapshot(InvalidCounts(), date(2026, 1, 6), date(2026, 1, 6), team_id="1")
    assert not snapshot.demands and not snapshot.shifts
    source = "SPDEM" if special else "SHDEM"
    assert any(m.startswith(source + " ") and "Besetzungszahl" in m
               and field.upper() in m for m in snapshot.unresolved)
    assert not any(m.startswith("SHIFT ") for m in snapshot.unresolved)


@pytest.mark.parametrize("special", [False, True])
@pytest.mark.parametrize("field", ["group_id", "shift_id", "workplace_id"])
@pytest.mark.parametrize("value", [True, False, 1.5, "1", [], {}, float("inf")])
def test_staffing_identity_is_checked_before_scope_and_cell_matching(special, field, value):
    class Source(SyntheticDatabase):
        def get_staffing_requirements(self):
            data = super().get_staffing_requirements()
            if special:
                data["shift_requirements"] = []
            else:
                data["shift_requirements"][0][field] = value
            return data

        def get_special_staffing(self, **kw):
            if not special:
                return []
            row = super().get_staffing_requirements()["shift_requirements"][0]
            return [{**row, "date": "2026-01-06", field: value}]

    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert not snapshot.demands
    source = "SPDEM" if special else "SHDEM"
    assert any(m.startswith(source + ":") and "Kennung" in m and field.upper() in m
               for m in snapshot.unresolved)
    key = "special_requirements" if special else "regular_requirements"
    assert len(snapshot.metadata["unresolved_native"][key]) == 1


@pytest.mark.parametrize("special", [False, True])
def test_integral_staffing_identities_normalize_before_building_ids(special):
    class Source(SyntheticDatabase):
        def get_staffing_requirements(self):
            data = super().get_staffing_requirements()
            if special:
                data["shift_requirements"] = []
            else:
                data["shift_requirements"][0].update(group_id=1.0, shift_id=201.0, workplace_id=301.0)
            return data

        def get_special_staffing(self, **kw):
            if not special:
                return []
            row = super().get_staffing_requirements()["shift_requirements"][0]
            return [{**row, "date": "2026-01-06", "group_id": 1.0, "shift_id": 201.0, "workplace_id": 301.0}]

    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert len(snapshot.demands) == 1
    assert snapshot.shifts[0].team_id == "sp5:group:1"
    assert snapshot.positions[0].function_id == "sp5:service:201"
    assert snapshot.positions[0].workplace_id == "sp5:workplace:301"


@pytest.mark.parametrize("group_id", [0, None, -1, 2])
def test_identity_guard_preserves_unscoped_and_other_team_semantics(group_id):
    class Source(SyntheticDatabase):
        def get_staffing_requirements(self):
            data = super().get_staffing_requirements()
            data["shift_requirements"][0]["group_id"] = group_id
            return data

    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert not snapshot.demands
    assert not any("Ungültige Kennung" in m for m in snapshot.unresolved)
    rows = snapshot.metadata["unresolved_native"].get("regular_requirements", [])
    assert len(rows) == int(group_id in (0, None))


def test_invalid_special_identity_cannot_replace_regular_cell():
    class Source(SyntheticDatabase):
        def get_special_staffing(self, **kw):
            row = super().get_staffing_requirements()["shift_requirements"][0]
            return [{**row, "date": "2026-01-06", "group_id": True, "min": 0, "max": 0}]

    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert len(snapshot.demands) == 1
    assert snapshot.demands[0].source == "sp5:SHDEM"
    assert snapshot.demands[0].minimum == 1
    assert len(snapshot.metadata["unresolved_native"]["special_requirements"]) == 1
    # Malformed special rows remain a blocker, not permission to use the fallback.
    from sp5generator.solver import solve
    result = solve(snapshot, 1, partial=True)
    assert result.solver_status == "MODEL_INVALID"
    assert not result.assignments


@pytest.mark.parametrize("conflict", ["HRSWEEK", "EMPEND"])
def test_employee_join_rejects_conflicting_source_rows(conflict):
    db = SyntheticDatabase()
    row = db.get_employees()[0]
    db.get_employees = lambda **kw: [row, {**row, conflict: 12 if conflict == "HRSWEEK" else "2026-01-02"}]
    with pytest.raises(ValueError, match="conflicting_employee"):
        import_snapshot(db, date(2026, 1, 5), date(2026, 1, 6), "1", "UTC")


def test_employee_join_rejects_orphan_membership():
    db = SyntheticDatabase()
    db.get_group_members = lambda group: [101, 102]
    with pytest.raises(ValueError, match="orphan_membership"):
        import_snapshot(db, date(2026, 1, 5), date(2026, 1, 6), "1", "UTC")


def test_employee_join_preserves_identical_rows_and_repeated_memberships():
    db = SyntheticDatabase()
    row = db.get_employees()[0]
    db.get_employees = lambda **kw: [row, dict(row)]
    db.get_group_members = lambda group: [101, 101]
    snapshot = import_snapshot(db, date(2026, 1, 5), date(2026, 1, 6), "1", "UTC")
    assert len(snapshot.employees) == 1


@pytest.mark.parametrize("bad_id", [True, False, [], {}, None, "101", 101.5, float("nan"), float("inf")])
@pytest.mark.parametrize("source", ["membership", "employee"])
def test_person_identity_checked_before_native_join(bad_id, source):
    db = SyntheticDatabase()
    if source == "membership":
        db.get_group_members = lambda group: [bad_id]
    else:
        row = db.get_employees()[0]
        db.get_employees = lambda **kw: [{**row, "ID": bad_id}]
    with pytest.raises(ValueError, match="invalid_person_identity"):
        import_snapshot(db, date(2026, 1, 5), date(2026, 1, 6), "1", "UTC")


def test_person_integral_dbf_float_identity_normalizes_without_losing_person():
    db = SyntheticDatabase()
    row = db.get_employees()[0]
    db.get_employees = lambda **kw: [{**row, "ID": 101.0}, row]
    db.get_group_members = lambda group: [101.0, 101]
    snapshot = import_snapshot(db, date(2026, 1, 5), date(2026, 1, 6), "1", "UTC")
    assert [e.id for e in snapshot.employees] == ["sp5:employee:101"]


@pytest.mark.parametrize("period_end", [date(2026, 1, 6), date(2026, 2, 26), date(2026, 2, 28)])
@pytest.mark.parametrize("window, spills", [("20:00-00:00", False), ("20:00-08:00", True)])
def test_final_context_day_overnight_preserves_extent_and_source_window(period_end, window, spills):
    """Preserve complete imported work without certifying unqueried context.

    The second period puts the last context day on the Vienna DST transition.
    This is an importer extent bug, not evidence that overnight duties are illegal.
    """
    from datetime import timedelta
    from sp5generator.domain import input_diagnostics

    last_source_day = period_end + timedelta(days=31)

    class Source(SyntheticDatabase):
        def get_shifts(self, **kw):
            rows = super().get_shifts(**kw)
            rows[0].update({f"STARTEND{i}": window for i in range(8)})
            return rows

        def get_schedule(self, year, month, **kw):
            if (year, month) != (last_source_day.year, last_source_day.month):
                return []
            return [{"employee_id": 101, "date": last_source_day.isoformat(),
                     "kind": "shift", "shift_id": 201, "workplace_id": 301}]

    source = Source()
    calls = []
    get_schedule = source.get_schedule

    def traced_schedule(year, month, **kw):
        calls.append((year, month))
        return get_schedule(year, month, **kw)

    source.get_schedule = traced_schedule
    snapshot = import_snapshot(source, period_end, period_end, "1", "Europe/Vienna")
    assert max(calls) == (last_source_day.year, last_source_day.month)
    work, = snapshot.boundary_work
    assert work.segments[0].start.date() == last_source_day
    assert work.segments[0].end.date() == last_source_day + timedelta(days=1)
    assert work.segments[0].end.hour == (8 if spills else 0)
    assert not snapshot.context_complete
    assert not snapshot.employees[0].approvals
    extent_end = last_source_day + timedelta(days=int(spills))
    assert snapshot.context_end == extent_end
    assert snapshot.profiles[0].valid_until == extent_end
    assert not snapshot.profiles[0].confirmed
    assert snapshot.metadata["context_source_window"] == {
        "start_date": (period_end - timedelta(days=31)).isoformat(),
        "end_date": last_source_day.isoformat(),
        "selection": "schedule_start_date",
        "complete": False,
    }
    assert any("Randkontext" in item for item in snapshot.unresolved)
    context_errors = [d for d in input_diagnostics(snapshot) if d.code == "context"]
    assert not context_errors
    if spills:
        shortened = snapshot.model_copy(update={"context_end": last_source_day})
        assert any(d.code == "context" for d in input_diagnostics(shortened))


@pytest.mark.parametrize("outside", [False, True])
@pytest.mark.parametrize("actual,paid,empty_nominal,elapsed", [
    ("20:00-08:00", 4, False, 720),
    ("08:00-10:00;11:00-13:00", 2, False, 240),
    ("06:00-08:00;18:00-20:00", 4, False, 240),
    ("08:00-13:00", 4, True, 300),
    ("08:00-08:00", 4, False, 1440),
])
def test_explicit_special_boundary_uses_actual_work_not_nominal(outside, actual, paid, empty_nominal, elapsed):
    """Known source times must not disappear or be replaced by the catalog."""
    from sp5generator.domain import input_diagnostics
    from sp5generator.timeutils import segments

    day = "2026-01-05" if outside else "2026-01-06"

    class Source(SyntheticDatabase):
        def get_shifts(self, **kw):
            rows = super().get_shifts(**kw)
            if empty_nominal:
                rows[0].update({f"STARTEND{i}": "" for i in range(8)})
            return rows

        def get_schedule(self, year, month, **kw):
            if (year, month) != (2026, 1):
                return []
            return [{"employee_id": 101, "date": day, "kind": kind,
                     "shift_id": 201, "workplace_id": 301, "spshi_type": 0}
                    for kind in ("shift", "special_shift")]

        def get_spshi_entries_for_day(self, date_str, **kw):
            return [{"id": 901, "employee_id": 101, "date": date_str,
                     "shift_id": 201, "workplace_id": 301, "type": 0,
                     "startend": actual, "duration": paid}]

    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert not snapshot.assignments  # Never invent a demand for special work.
    assert not snapshot.employees[0].approvals
    assert not snapshot.profiles[0].confirmed
    assert not snapshot.context_complete
    assert len(snapshot.metadata["context_schedule"]) == 2  # Original rows retained.
    if outside:
        work, = snapshot.boundary_work
        assert work.kind == "unknown"  # Actual time is not day/night confirmation.
        source = snapshot.metadata["provenance"][work.id]
        assert source["time_source"] == "sp5:SPSHI.STARTEND"
        assert source["paid_minutes"] == paid * 60
        assert len(source["replaced_normal_rows"]) == 1
        assert sum(b - a for a, b in segments(work)) == elapsed
        assert not any(text.startswith("Sonderdienst") for text in snapshot.unresolved)
        assert "boundary_kind" in {d.code for d in input_diagnostics(snapshot)}
    else:
        # In-period paid work is modelled, not bypassed: the source times and
        # paid minutes are kept, the person is blocked, and no demand is covered.
        work, = snapshot.boundary_work
        assert work.in_period and work.kind == "unknown"
        assert work.paid_minutes == paid * 60
        assert sum(b - a for a, b in segments(work)) == elapsed
        source = snapshot.metadata["provenance"][work.id]
        assert source["time_source"] == "sp5:SPSHI.STARTEND"
        assert source["paid_minutes"] == paid * 60
        assert not any(text.startswith("Sonderdienst") for text in snapshot.unresolved)
        assert any("als persönliche Arbeit" in text for text in snapshot.unresolved)
        codes = {d.code for d in input_diagnostics(snapshot)}
        assert "boundary_kind" in codes and "boundary_period" not in codes


@pytest.mark.parametrize("actual,paid", [
    ("", 4), ("invalid", 4), ("20:00-08:00", None),
    ("20:00-08:00", -1), ("20:00-08:00", "NaN"),
])
def test_special_boundary_missing_or_invalid_details_never_reuses_nominal(actual, paid):
    class Source(SyntheticDatabase):
        def get_schedule(self, year, month, **kw):
            if (year, month) != (2026, 1):
                return []
            return [{"employee_id": 101, "date": "2026-01-05", "kind": kind,
                     "shift_id": 201, "workplace_id": 301, "spshi_type": 0,
                     "startend": actual, "duration": paid}
                    for kind in ("shift", "special_shift")]

    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert not snapshot.boundary_work
    assert not snapshot.assignments
    assert any(text.startswith("Sonderdienst") for text in snapshot.unresolved)


@pytest.mark.parametrize("day,period,expected", [
    ("2026-03-28", date(2026, 3, 29), 9 * 60),
    ("2026-10-24", date(2026, 10, 25), 11 * 60),
])
def test_special_boundary_preserves_real_dst_duration_independently_of_paid(day, period, expected):
    from sp5generator.timeutils import day_minutes

    class Source(SyntheticDatabase):
        def get_schedule(self, year, month, **kw):
            if month != period.month:
                return []
            return [{"employee_id": 101, "date": day, "kind": "special_shift",
                     "shift_id": 201, "workplace_id": 301, "spshi_type": 0,
                     "startend": "22:00-08:00", "duration": 2}]

    snapshot = import_snapshot(Source(), period, period, "1", "Europe/Vienna")
    work, = snapshot.boundary_work
    assert sum(day_minutes(work, snapshot.timezone).values()) == expected
    assert snapshot.metadata["provenance"][work.id]["paid_minutes"] == 120
    assert work.segments[0].end.hour == 8
    assert work.kind == "unknown"


def test_distinct_special_boundary_windows_do_not_collapse_by_service_and_workplace():
    class Source(SyntheticDatabase):
        def get_schedule(self, year, month, **kw):
            if (year, month) != (2026, 1):
                return []
            return [{"employee_id": 101, "date": "2026-01-05", "kind": "special_shift",
                     "shift_id": 201, "workplace_id": 301, "spshi_type": 0,
                     "startend": value, "duration": 2}
                    for value in ("06:00-08:00", "18:00-20:00", "06:00-08:00")]

    snapshot = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert len(snapshot.boundary_work) == 2  # Identical source row counted once.
    assert len({v.id for v in snapshot.boundary_work}) == 2
    assert {v.segments[0].start.hour for v in snapshot.boundary_work} == {6, 18}
    assert not snapshot.assignments


@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("rule", ["daily_limit", "weekly_limit", "rest"])
def test_imported_special_boundary_enforces_actual_time_in_solver_and_validator(rule, partial):
    from sp5generator.models import Assignment
    from sp5generator.solver import solve
    from sp5generator.validator import validate
    from test_core_rules import case, shift

    class Source(SyntheticDatabase):
        def get_schedule(self, year, month, **kw):
            if (year, month) != (2026, 1):
                return []
            return [{"employee_id": 101, "date": "2026-01-05", "kind": "special_shift",
                     "shift_id": 201, "workplace_id": 301, "spshi_type": 0,
                     "startend": "20:00-08:00", "duration": 4}]

    imported = import_snapshot(Source(), date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    work, = imported.boundary_work  # 12 actual hours, only 4 paid source hours.
    # Separate explicitly configured synthetic project, not clearing import
    # blockers or claiming permission to confirm real source classifications.
    snapshot = case(1, [shift("new", 6, 12, 4)])
    snapshot.period_start = snapshot.period_end = date(2026, 1, 6)
    snapshot.boundary_work = [work.model_copy(update={"employee_id": "e0", "kind": "night"})]
    profile = snapshot.profiles[0]
    profile.min_rest_minutes = 241 if rule == "rest" else 0
    if rule == "daily_limit":
        profile.max_daily_minutes = 719  # 8 context + 4 new actual hours.
    elif rule == "weekly_limit":
        profile.max_weekly_minutes = 959  # 12 context + 4 new actual hours.
    proposed = [Assignment(employee_id="e0", demand_id="new")]
    assert validate(snapshot, []).valid
    assert rule in {d.code for d in validate(snapshot, proposed).diagnostics}
    result = solve(snapshot, 5, partial=partial)
    assert result.solver_status == ("OPTIMAL" if partial else "INFEASIBLE")
    assert not result.assignments
    assert result.validation.valid is partial
    # Counterfactual proves that dropping the actual work loses this protection.
    without_context = snapshot.model_copy(update={"boundary_work": []})
    assert validate(without_context, proposed).complete


class UntimedServiceDatabase(SyntheticDatabase):
    """A catalog service the source states paid hours but no times for."""

    def get_shifts(self, **kw):
        return super().get_shifts(**kw) + [{
            "ID": 202,
            "NAME": "Backoffice",
            **{f"STARTEND{i}": "" for i in range(8)},
            **{f"DURATION{i}": 8 for i in range(8)},
        }]

    def get_schedule(self, year, month, **kw):
        if (year, month) != (2026, 1):
            return []
        return [{"employee_id": 101, "date": day, "kind": "shift",
                 "shift_id": 202, "workplace_id": 301, "spshi_type": 0}
                for day in self.days]


def test_observed_demand_skips_untimed_cells_and_preserves_personal_work():
    source = UntimedServiceDatabase()
    source.days = ["2026-01-05", "2026-01-06", "2026-01-06"]
    baseline = import_snapshot(source, date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    snapshot = import_snapshot(
        source, date(2026, 1, 6), date(2026, 1, 6), "1", "UTC", demand_source="observed"
    )
    assert not snapshot.demands
    assert snapshot.metadata["observed_demand"] == {"cells": 0, "slots": 0, "skipped": 1}
    assert snapshot.boundary_work == baseline.boundary_work
    assert snapshot.employees == baseline.employees
    assert snapshot.metadata["untimed_period_work"] == baseline.metadata["untimed_period_work"] == 1
    assert snapshot.metadata["untimed_context_work"] == baseline.metadata["untimed_context_work"] == 1
    assert len([message for message in snapshot.unresolved if "abgeleitet" in message]) == 1


def test_untimed_service_inside_the_period_stays_personal_work():
    from sp5generator.domain import input_diagnostics

    source = UntimedServiceDatabase()
    source.days = ["2026-01-06"]
    snapshot = import_snapshot(source, date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    work, = snapshot.boundary_work
    assert work.day == date(2026, 1, 6) and not work.segments
    assert work.in_period and work.paid_minutes == 8 * 60 and work.holiday
    origin = snapshot.metadata["provenance"][work.id]
    assert origin["time_source"] == "sp5:SHIFT.STARTEND7 ohne Zeitangabe"
    assert origin["paid_source"] == "sp5:SHIFT.DURATION7"
    assert snapshot.metadata["untimed_period_work"] == 1
    assert not snapshot.assignments  # Never invent a demand for personal work.
    assert any("keine Uhrzeiten angibt" in text for text in snapshot.unresolved)
    assert not any(text.startswith("Bestehender Dienst") for text in snapshot.unresolved)
    # Without times there is no day or night to confirm and no invalid interval.
    codes = {d.code for d in input_diagnostics(snapshot)}
    assert not codes & {"boundary_kind", "boundary_period", "interval"}


def test_untimed_service_outside_the_period_is_reported_once():
    source = UntimedServiceDatabase()
    source.days = ["2026-01-02", "2026-01-03", "2026-01-05"]
    snapshot = import_snapshot(source, date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert not snapshot.boundary_work  # No times, nothing to place in the context.
    assert snapshot.metadata["untimed_context_work"] == 3
    assert snapshot.metadata["untimed_period_work"] == 0
    assert sum("Ruhezeit vor oder nach" in text for text in snapshot.unresolved) == 1
    assert not any(text.startswith("Bestehender Dienst") for text in snapshot.unresolved)


def test_missing_day_window_of_a_timed_service_stays_an_open_note():
    """Only a service without any times is personal work; a gap stays a gap."""
    class Source(UntimedServiceDatabase):
        def get_shifts(self, **kw):
            rows = super().get_shifts(**kw)
            rows[-1].update({f"STARTEND{i}": "08:00-16:00" for i in range(7)})
            return rows

    source = Source()
    source.days = ["2026-01-05", "2026-01-06"]
    snapshot = import_snapshot(source, date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    # 05.01. is a Monday the catalog states times for; 06.01. uses the holiday
    # index, which it does not. Each day keeps the shape its own source has.
    timed, = [w for w in snapshot.boundary_work if w.segments]
    untimed, = [w for w in snapshot.boundary_work if not w.segments]
    assert timed.day is None and not timed.in_period
    assert untimed.day == date(2026, 1, 6) and untimed.in_period
    assert snapshot.metadata["untimed_period_work"] == 1
    assert snapshot.metadata["untimed_context_work"] == 0
