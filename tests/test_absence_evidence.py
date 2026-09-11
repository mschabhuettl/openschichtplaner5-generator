"""Synthetic source-account cases; no automatic credit or invented hard cap."""

from datetime import date

import pytest

pytest.importorskip("sp5lib")
from sp5generator.sp5_adapter import import_snapshot
from sp5generator.api_adapter import APIClient, APIImportError, _Database, import_api
from test_sp5_adapter import SyntheticDatabase
from test_api_adapter import transport  # noqa: F401


def absence(**changes):
    return {"employee_id": 101, "kind": "absence", "date": "2026-01-07",
            "leave_type_id": 7, "interval": 0, **changes}


def source_import(rows, definition=None, holidays=None, **employee):
    class Source(SyntheticDatabase):
        def get_employees(self, **kw):
            return [{**super().get_employees(**kw)[0], **employee}]

        def get_leave_types(self, include_hidden=False):
            assert include_hidden is True
            return [{"ID": 7, "CHARGETYP": 1, "HIDE": True, **(definition or {})}]

        def get_holidays(self):
            return super().get_holidays() if holidays is None else holidays

        def get_schedule(self, year, month, **kw):
            return rows if (year, month) == (2026, 1) else []

    return import_snapshot(Source(), date(2026, 1, 5), date(2026, 1, 11), "1")


def evidence(snapshot):
    return snapshot.metadata["provenance"]["sp5:employee:101"]["absence_accounting"]


@pytest.mark.parametrize("row,definition,employee,expected", [
    (absence(), {}, {}, (8, 0, 0)),
    (absence(interval=1), {}, {}, (4, 0, 0)),
    (absence(interval=2), {"CHARGETYP": 2, "CHARGEHRS": 6}, {}, (3, 0, 0)),
    (absence(interval=3, start_time=1320, end_time=120), {}, {}, (4, 0, 0)),
    (absence(), {"DEDUCTACT": True, "DEDUCTOVT": True}, {}, (0, 8, 8)),
    (absence(), {"CHARGETYP": 0, "DEDUCTOVT": True}, {}, (0, 0, 8)),
    (absence(date="2026-01-10"), {}, {}, (0, 0, 0)),
    (absence(date="2026-01-10"), {"COUNTALL": True}, {}, (8, 0, 0)),
    (absence(date="2026-01-06"), {}, {}, (0, 0, 0)),
    (absence(date="2026-01-06"), {"COUNTALL": True}, {}, (8, 0, 0)),
    (absence(), {}, {"EMPSTART": "2026-01-08"}, (0, 0, 0)),
    (absence(), {}, {"EMPEND": "2026-01-06"}, (0, 0, 0)),
])
def test_dated_library_evaluation_is_not_a_credit(row, definition, employee, expected):
    snapshot = source_import([row], definition, **employee)
    origin = evidence(snapshot)
    assert origin["applied"] is False
    assert origin["source"] == "deduplicated_schedule_without_absen_ids"
    item, = origin["rows"]
    assert item["status"] == "evaluated"
    assert item["hours"] == dict(zip(
        ("charged", "charged_deduct_actual", "raw_deduct_overtime"), expected,
    ))
    person = snapshot.employees[0]
    assert person.credit_minutes == person.balance_minutes == 0
    assert person.approvals == []
    assert all(p.max_weekly_minutes is None and not p.confirmed for p in snapshot.profiles)
    assert snapshot.model_validate_json(snapshot.model_dump_json()).metadata == snapshot.metadata


@pytest.mark.parametrize("changes,reason", [
    ({"leave_type_id": None}, "missing_leave_type_definition"),
    ({"leave_type_id": 99}, "missing_leave_type_definition"),
    ({"interval": 9}, "invalid_interval"),
    ({"interval": 3, "start_time": 600, "end_time": 600}, "invalid_interval"),
    ({"interval": 3, "start_time": "bad", "end_time": 700}, "invalid_interval"),
])
def test_unresolved_is_not_reported_as_zero(changes, reason):
    item, = evidence(source_import([absence(**changes)]))["rows"]
    assert item["status"] == "unresolved" and item["reason"] == reason
    assert "hours" not in item


def test_scope_duplicates_and_no_free_text():
    snapshot = source_import([
        absence(note="private annotation"), absence(note="different annotation"),
        absence(date="2026-01-04"), absence(employee_id=999),
    ])
    assert len(evidence(snapshot)["rows"]) == 1
    assert "annotation" not in snapshot.model_dump_json()


@pytest.mark.parametrize("interval,start,end,expected", [
    (0, 0, 0, 4), (1, 0, 0, 0), (2, 0, 0, 4), (3, 600, 840, 2),
])
def test_half_holiday_uses_library_clipping(interval, start, end, expected):
    snapshot = source_import(
        [absence(interval=interval, start_time=start, end_time=end)],
        holidays=[{"DATE": "2026-01-07", "INTERVAL": 1}],
    )
    assert evidence(snapshot)["rows"][0]["hours"]["charged"] == expected


def test_missing_source_is_not_a_confirmed_zero():
    snapshot = import_snapshot(SyntheticDatabase(), date(2026, 1, 5), date(2026, 1, 5), "1")
    item, = evidence(snapshot)["rows"]
    assert item["status"] == "unresolved"
    assert "hours" not in item


def test_http_definitions_include_hidden_and_stay_read_only(transport):  # noqa: F811
    responses, calls = transport
    responses["/api/leave-types"] = [{"ID": 7, "CHARGETYP": 1, "COUNTALL": True, "HIDE": True}]
    responses[("schedule", "2026", "1", "ist")] = [absence(date="2026-01-06")]
    snapshot = import_api(date(2026, 1, 6), date(2026, 1, 6), "1")
    item, = evidence(snapshot)["rows"]
    assert item["hours"]["charged"] == 8
    assert any("/api/leave-types?include_hidden=true" in c.full_url for c in calls)
    assert all(c.get_method() == "GET" for c in calls)


def test_http_definition_format_failure_is_not_missing_access(transport):  # noqa: F811
    responses, _ = transport
    responses["/api/leave-types"] = {"error": "synthetic failure"}
    with pytest.raises(APIImportError, match="Listenformat"):
        _Database(APIClient(), "1").get_leave_types(include_hidden=True)
