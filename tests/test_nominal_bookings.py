"""Synthetic BOOK facade/API regressions; never load private source records."""

from datetime import date

import pytest

pytest.importorskip("sp5lib")
from sp5generator.sp5_adapter import import_snapshot
from sp5generator.api_adapter import APIImportError, import_api
from test_sp5_adapter import SyntheticDatabase
from test_api_adapter import transport as booking_transport  # noqa: F401


def booking(value=2, **changes):
    return {"employee_id": 101, "date": "2026-01-06", "type": 1,
            "value": value, **changes}


def imported(rows, start=date(2026, 1, 6), end=date(2026, 1, 6), **employee):
    class Source(SyntheticDatabase):
        calls = []

        def get_bookings(self, **params):
            self.calls.append(params)
            return rows

        def get_employees(self, **kw):
            return [{**super().get_employees(**kw)[0], **employee}]

    source = Source()
    return import_snapshot(source, start, end, team_id="1"), source.calls


def origin(snapshot):
    return snapshot.metadata["provenance"][snapshot.employees[0].id]["nominal_hours"]


def test_signed_nominal_bookings_are_scoped_not_credits_or_weekly_caps():
    snapshot, calls = imported([
        booking(3), booking(-1), booking(100, type=0),
        booking(100, employee_id=999), booking(100, date="2026-01-07"),
    ])
    person = snapshot.employees[0]
    assert person.target_minutes == 120
    assert person.credit_minutes == person.balance_minutes == 0
    assert person.approvals == []
    assert all(p.max_weekly_minutes is None for p in snapshot.profiles)
    assert origin(snapshot)["nominal_booking_count"] == 2
    assert origin(snapshot)["nominal_booking_minutes"] == 120
    assert origin(snapshot)["bookings_included"] is True
    assert calls == [{"year": 2026, "month": 1}]
    assert not any("Sollbuchungen" in s for s in snapshot.unresolved)
    assert any("Zeitgutschriften" in s for s in snapshot.unresolved)


def test_bookings_count_before_employment_clamp():
    snapshot, _ = imported([booking()], EMPSTART="2026-01-07")
    assert snapshot.employees[0].target_minutes == 120


def test_actual_booking_evidence_preserves_signed_dates_without_applying():
    snapshot, calls = imported([
        booking(-2, type=0, id=41, note="not needed for provenance"),
        booking(3, type=0, id=42), booking(3, type=0, id=43),
        booking(100, type=0, employee_id=999),
        booking(100, type=0, date="2026-01-01"), booking(100, type=2),
    ], EMPSTART="2026-01-07")
    person = snapshot.employees[0]
    evidence = snapshot.metadata["provenance"][person.id]["actual_bookings"]
    assert evidence == {
        "table": "BOOK", "period_start": "2026-01-06", "period_end": "2026-01-06",
        "applied": False, "classification": "unresolved", "rows": [
            {"date": "2026-01-06", "type": 0, "value_hours": -2.0, "source_id": 41},
            {"date": "2026-01-06", "type": 0, "value_hours": 3.0, "source_id": 42},
            {"date": "2026-01-06", "type": 0, "value_hours": 3.0, "source_id": 43},
        ],
    }
    assert person.credit_minutes == person.balance_minutes == person.target_minutes == 0
    assert calls == [{"year": 2026, "month": 1}]
    assert snapshot.model_validate_json(snapshot.model_dump_json()).metadata == snapshot.metadata


@pytest.mark.parametrize("value", [None, "", True, "nan", "inf", "invalid"])
def test_invalid_actual_booking_evidence_is_not_silently_lost(value):
    with pytest.raises(ValueError):
        imported([booking(value, type=0)])


@pytest.mark.parametrize("adjustment", [-10, -2, 2, 10])
def test_actual_account_is_not_a_replanning_credit(adjustment):
    """Source actual totals include work; importing the total would count it twice."""
    from sp5lib import calculations as calc

    day = date(2026, 1, 6)
    employee = calc.EmployeeContext(
        workdays=(True, True, True, True, True, False, False, False),
        calcbase=0, hrs_day=8,
    )
    rows = [
        {"DATE": day.isoformat(), "TYPE": 0, "VALUE": adjustment},
        {"DATE": "2026-01-01", "TYPE": 0, "VALUE": 100},
        {"DATE": day.isoformat(), "TYPE": 1, "VALUE": 3},
        {"DATE": day.isoformat(), "TYPE": 2, "VALUE": 100},
    ]
    kwargs = dict(
        holidays={}, shifts_by_id={1: {"STARTEND1": "06:00-14:00", "DURATION1": 8}},
        bookings=rows,
    )
    without_work = calc.get_actual_hours(employee, day, day, **kwargs)
    with_work = calc.get_actual_hours(
        employee, day, day,
        manual_shifts=[{"DATE": day.isoformat(), "SHIFTID": 1}], **kwargs,
    )
    assert without_work == adjustment
    assert with_work == 8 + adjustment
    assert calc.get_nominal_hours(employee, day, day, holidays={}, bookings=rows) == 11

    snapshot, _ = imported([
        booking(adjustment, type=0), booking(100, type=0, date="2026-01-01"),
        booking(3), booking(100, type=2),
    ])
    # Current explicit mapping gap: do not silently interpret an actual total,
    # signed correction, or a January carry-in as a confirmed opening balance.
    person = snapshot.employees[0]
    assert person.credit_minutes == person.balance_minutes == 0
    assert any("Zeitgutschriften" in message for message in snapshot.unresolved)
    assert all(profile.max_weekly_minutes is None for profile in snapshot.profiles)


def test_equal_bookings_remain_distinct_and_round_only_after_summing():
    snapshot, _ = imported([booking(0.006), booking(0.006)])
    assert snapshot.employees[0].target_minutes == 1
    assert origin(snapshot)["nominal_booking_count"] == 2
    assert origin(snapshot)["nominal_booking_minutes"] == 1


def test_negative_source_target_is_preserved_and_blocks_planning():
    snapshot, _ = imported([booking(-2)])
    assert snapshot.employees[0].target_minutes == 0
    assert origin(snapshot)["source_target_minutes"] == -120
    assert any("Negatives Quell-Soll" in s for s in snapshot.unresolved)
    from sp5generator.domain import input_diagnostics
    assert any(d.code == "unresolved" and "Negatives Quell-Soll" in d.message
               for d in input_diagnostics(snapshot))


def test_months_and_year_boundary_do_not_double_count_unfiltered_rows():
    snapshot, calls = imported([
        booking(2, date="2025-12-31"), booking(3, date="2026-01-01"),
        booking(99, date="2026-01-02"),
    ], date(2025, 12, 31), date(2026, 1, 1), EMPSTART="2027-01-01")
    assert snapshot.employees[0].target_minutes == 300
    assert calls == [{"year": 2025, "month": 12}, {"year": 2026, "month": 1}]


def test_known_empty_and_unavailable_sources_remain_distinct():
    empty, _ = imported([])
    missing = import_snapshot(SyntheticDatabase(), date(2026, 1, 6), date(2026, 1, 6), team_id="1")
    assert origin(empty)["bookings_included"] is True
    assert origin(missing)["bookings_included"] is False
    empty_provenance = empty.metadata["provenance"][empty.employees[0].id]
    missing_provenance = missing.metadata["provenance"][missing.employees[0].id]
    assert empty_provenance["actual_bookings"]["rows"] == []
    assert "actual_bookings" not in missing_provenance
    assert any("Sollbuchungen nicht verfügbar" in s for s in missing.unresolved)


def test_real_library_missing_book_table_is_not_known_empty(tmp_path):
    from sp5lib.database import SP5Database
    from sp5generator.sp5_adapter import _nominal_bookings
    from test_sp5_dbf import empty_table
    source = SP5Database(str(tmp_path))
    day = date(2026, 1, 6)
    assert _nominal_bookings(source, [{"ID": 101}], day, day) is None
    empty_table(tmp_path / "5BOOK.DBF", [("ID", "N", 8), ("EMPLOYEEID", "N", 8),
                                       ("DATE", "D", 8), ("TYPE", "N", 8), ("VALUE", "N", 8)])
    assert _nominal_bookings(source, [{"ID": 101}], day, day) == {101: []}


@pytest.mark.parametrize("broken", [b"", b"truncated"])
def test_truncated_book_table_is_not_known_empty(tmp_path, broken):
    from sp5lib.database import SP5Database
    from sp5generator.sp5_adapter import _nominal_bookings
    (tmp_path / "5BOOK.DBF").write_bytes(broken)
    with pytest.raises(ValueError, match="Buchung"):
        _nominal_bookings(SP5Database(str(tmp_path)), [{"ID": 101}],
                          date(2026, 1, 6), date(2026, 1, 6))


def test_missing_book_fields_are_not_known_empty(tmp_path):
    from sp5lib.database import SP5Database
    from sp5generator.sp5_adapter import _nominal_bookings
    from test_sp5_dbf import empty_table
    empty_table(tmp_path / "5BOOK.DBF", [("ID", "N", 8)])
    with pytest.raises(ValueError, match="Pflichtfelder"):
        _nominal_bookings(SP5Database(str(tmp_path)), [{"ID": 101}],
                          date(2026, 1, 6), date(2026, 1, 6))


def test_unreadable_book_is_not_known_empty(tmp_path, monkeypatch):
    from sp5lib.database import SP5Database
    from sp5generator.sp5_adapter import _nominal_bookings
    original = open

    def denied(path, *args, **kwargs):
        if str(path).endswith("5BOOK.DBF"):
            raise PermissionError("synthetic access failure")
        return original(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", denied)
    with pytest.raises(ValueError, match="nicht lesbar"):
        _nominal_bookings(SP5Database(str(tmp_path)), [{"ID": 101}],
                          date(2026, 1, 6), date(2026, 1, 6))


def test_real_library_normalizes_signed_dbf_book_rows(tmp_path):
    from sp5lib.database import SP5Database
    from sp5lib.dbf_reader import get_table_fields
    from sp5lib.dbf_writer import append_record
    from sp5generator.sp5_adapter import _nominal_bookings
    from test_sp5_dbf import empty_table
    path = tmp_path / "5BOOK.DBF"
    empty_table(path, [("ID", "N", 8), ("EMPLOYEEID", "N", 8),
                       ("DATE", "D", 8), ("TYPE", "N", 8), ("VALUE", "N", 8)])
    fields = get_table_fields(str(path))
    append_record(str(path), fields, {"ID": 1, "EMPLOYEEID": 101,
                                     "DATE": "2026-01-06", "TYPE": 1, "VALUE": -2})
    day = date(2026, 1, 6)
    assert _nominal_bookings(SP5Database(str(tmp_path)), [{"ID": 101}], day, day) == {
        101: [{"DATE": "2026-01-06", "TYPE": 1, "VALUE": -2.0}]
    }


@pytest.mark.parametrize("rows", [None, {}, [None], [{}], [booking(date="bad")],
                                     [booking(value=None)], [booking(value=float("nan"))],
                                     [booking(value="")], [booking(employee_id=None)],
                                     [booking(type=None)], [booking(type=1.5)]])
def test_malformed_source_is_not_a_confirmed_empty_list(rows):
    with pytest.raises((ValueError, TypeError, KeyError)):
        imported(rows)


def test_api_bookings_use_get_and_participate_in_consistency_check(booking_transport):  # noqa: F811
    responses, calls = booking_transport
    responses["/api/bookings"] = [booking(), booking(-3, type=0, id=42)]
    snapshot = import_api(date(2026, 1, 6), date(2026, 1, 6), "1")
    assert snapshot.employees[0].target_minutes == 120
    assert snapshot.metadata["provenance"][snapshot.employees[0].id]["actual_bookings"]["rows"] == [
        {"date": "2026-01-06", "type": 0, "value_hours": -3.0, "source_id": 42},
    ]
    paths = [r.full_url for r in calls if "/api/bookings" in r.full_url]
    assert len(paths) == 2  # cached import + independent repeat comparison
    assert all("year=2026&month=1" in path for path in paths)


@pytest.mark.parametrize("status", [403, 404])
def test_booking_access_failure_never_means_zero(booking_transport, monkeypatch, status):  # noqa: F811
    from sp5generator.api_adapter import APIClient
    original = APIClient._read

    def read(self, path):
        if path.startswith("/api/bookings"):
            raise APIImportError(f"API-Anfrage abgelehnt (HTTP {status})")
        return original(self, path)

    monkeypatch.setattr(APIClient, "_read", read)
    with pytest.raises(APIImportError, match=f"HTTP {status}"):
        import_api(date(2026, 1, 6), date(2026, 1, 6), "1")
