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
