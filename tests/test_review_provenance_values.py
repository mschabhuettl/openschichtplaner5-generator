"""DATA-R2-01: optional labels cannot change work or break portable exports.

All fixtures are synthetic; both formats are written and independently read.
The scalar contract follows the producer: name/function_id are strings;
workplace_id additionally permits exact, Excel-safe native integers, not bool.
"""
import csv
import json
from datetime import UTC, datetime, timedelta

import pytest
from openpyxl import load_workbook

from sp5generator.domain import input_diagnostics
from sp5generator.export import export_table
from sp5generator.export_work import export_work
from sp5generator.models import Assignment, BoundaryWork, Interval, Snapshot
from test_review_data_followup import checked_result, snapshot_for_review


WORK_ID = " exact personal\u00a0ID 000301 "
FIELDS = {"name": 5, "function_id": 3, "workplace_id": 4}
GOOD_LABELS = {"name": "Synthetic personal duty", "function_id": "role-001", "workplace_id": "000301"}


def personal_snapshot(source):
    snapshot = snapshot_for_review(days=1)
    snapshot.employees = [snapshot.employees[1]]
    employee = snapshot.employees[0]
    employee.target_minutes, employee.credit_minutes, employee.balance_minutes = 180, 40, -25
    snapshot.shifts, snapshot.demands = [], []
    snapshot.boundary_work = [BoundaryWork(
        id=WORK_ID, employee_id=employee.id, segments=[], day=snapshot.period_start,
        paid_minutes=120,
    )]
    snapshot.metadata = {"provenance": {WORK_ID: source}}
    # Use the public model contract, including Python values accepted by Any.
    snapshot = Snapshot.model_validate(snapshot.model_dump())
    assert input_diagnostics(snapshot) == []
    return snapshot


def read_export(tmp_path, snapshot, suffix, assignments=()):
    result = checked_result(snapshot, list(assignments))
    assert result.validation.valid and result.validation.complete
    before = json.dumps(snapshot.model_dump(), sort_keys=True, default=str)
    plan_before = result.model_dump()
    target = tmp_path / f"synthetic.{suffix}"
    previous = b"previous synthetic export"
    target.write_bytes(previous)
    try:
        export_table(snapshot, result, target)
    except Exception:
        # A failed reproduction must never have destroyed its prior destination.
        assert target.read_bytes() == previous
        raise
    assert json.dumps(snapshot.model_dump(), sort_keys=True, default=str) == before
    assert result.model_dump() == plan_before
    assert set(tmp_path.iterdir()) == {target}
    if suffix == "csv":
        with target.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        return rows, None, None
    book = load_workbook(target, data_only=False)
    try:
        assert all(cell.data_type != "f" for sheet in book for row in sheet for cell in row)
        rows = list(book["Einteilungen"].values)
        calendar = {cell.coordinate: cell.value for row in book.active for cell in row}
        balances = {cell.coordinate: cell.value for row in book["Stundenübersicht"] for cell in row}
    finally:
        book.close()
    return rows, calendar, balances


def protected(value):
    # Independent assertion of the pre-existing formula protection contract.
    return "'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value


def assert_personal_readback(rows, calendar, balances, snapshot, suffix, expected):
    detail = [row for row in rows if len(row) >= 12 and row[2] == WORK_ID]
    assert len(detail) == 1
    row = detail[0]
    for field, column in FIELDS.items():
        value = protected(expected[field])
        assert row[column] == (str(value) if suffix == "csv" else None if value == "" else value)
    assert row[0] == "candidate"
    assert row[2] == WORK_ID
    assert int(row[8]) == 120
    assert row[6:8] == (["", ""] if suffix == "csv" else (None, None))
    assert row[10] == "Persönliche Arbeit ohne Zeiten"
    assert row[11] == str(snapshot.period_start)
    totals = next(row for row in rows if row and row[0] == "candidate" and row[1] in ("180", 180))
    assert tuple(int(value) for value in totals[1:4]) == (180, 160, -45)
    if suffix == "xlsx":
        title = "◆ " + expected["name"]
        if expected["name"] != "Persönliche Arbeit":
            title += " · Persönliche Arbeit"
        assert calendar["B5"] == title + "\nohne Zeiten"
        assert balances["C5"] == 2
        assert balances["D5"] == pytest.approx(40 / 60)
        assert balances["E5"] == pytest.approx(-25 / 60)
        assert balances["F5"] == -0.75
        assert balances["G5"] == 1
    entries = list(export_work(snapshot, []))
    assert len(entries) == 1
    assert entries[0].work is snapshot.boundary_work[0]
    assert entries[0].reference_id == WORK_ID
    assert entries[0].period_paid_minutes == 120
    assert {field: getattr(entries[0], field) for field in FIELDS} == expected


SCALAR_VALUES = [
    pytest.param(None, id="null"),
    pytest.param([], id="empty-list"),
    pytest.param(["optional", "label"], id="list"),
    pytest.param({}, id="empty-dict"),
    pytest.param({"optional": "label"}, id="dict"),
    pytest.param(False, id="false"),
    pytest.param(True, id="true"),
    pytest.param(0, id="zero"),
    pytest.param(17, id="positive-int"),
    pytest.param(-17, id="negative-int"),
    pytest.param(999_999_999_999_999, id="max-exact-native-int"),
    pytest.param(-999_999_999_999_999, id="min-exact-native-int"),
    pytest.param(1_000_000_000_000_000, id="too-many-digits"),
    pytest.param(10 ** 400, id="huge-int"),
    pytest.param(0.0, id="float-zero"),
    pytest.param(17.0, id="integral-float"),
    pytest.param(17.5, id="fractional-float"),
    pytest.param(float("nan"), id="nan"),
    pytest.param(float("inf"), id="infinity"),
    pytest.param(float("-inf"), id="negative-infinity"),
    pytest.param("", id="empty-string"),
    pytest.param("  Ä ß λ 🧪 e\u0301\u00a0 ", id="exact-unicode"),
    pytest.param("000301", id="leading-zeros"),
    pytest.param("=1+1", id="formula-equals"),
    pytest.param(" \t+SUM(A1:A2)", id="formula-whitespace-plus"),
    pytest.param("-literal", id="formula-minus"),
    pytest.param("@literal", id="formula-at"),
    pytest.param("#REF!", id="excel-error-like"),
]


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("value", SCALAR_VALUES)
def test_optional_provenance_scalar_contract(tmp_path, suffix, field, value):
    snapshot = personal_snapshot({**GOOD_LABELS, field: value})
    expected = dict(GOOD_LABELS)
    accepted_integer = field == "workplace_id" and type(value) is int and abs(value) <= 999_999_999_999_999
    expected[field] = value if isinstance(value, str) or accepted_integer else ""
    if not expected["name"]:
        expected["name"] = "Persönliche Arbeit"
    rows, calendar, balances = read_export(tmp_path, snapshot, suffix)
    assert_personal_readback(rows, calendar, balances, snapshot, suffix, expected)


UNUSABLE_TEXT = [
    pytest.param(" \t\n\r\u00a0", id="whitespace-only"),
    pytest.param("label\x00", id="nul"),
    pytest.param("label\x01", id="control"),
    pytest.param("label\x0b", id="vertical-tab"),
    pytest.param("label\x0c", id="form-feed"),
    pytest.param("label\x1f", id="unit-separator"),
    # The offline XLSX writer normalizes raw CR to LF when read back. Treat
    # this optional string as unusable rather than silently changing it.
    pytest.param("label\r", id="carriage-return"),
    pytest.param("\t=literal\r\n", id="formula-with-crlf"),
    pytest.param("label\ud800", id="high-surrogate"),
    pytest.param("label\udfff", id="low-surrogate"),
    pytest.param("label\ufffe", id="xml-noncharacter-fffe"),
    pytest.param("label\uffff", id="xml-noncharacter-ffff"),
    pytest.param("x" * 32768, id="overlong"),
    pytest.param("=" + "x" * 32766, id="overlong-after-formula-protection"),
]


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("value", UNUSABLE_TEXT)
def test_optional_unusable_text_falls_back_in_both_formats(tmp_path, suffix, field, value):
    snapshot = personal_snapshot({**GOOD_LABELS, field: value})
    expected = {**GOOD_LABELS, field: "Persönliche Arbeit" if field == "name" else ""}
    rows, calendar, balances = read_export(tmp_path, snapshot, suffix)
    assert_personal_readback(rows, calendar, balances, snapshot, suffix, expected)


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("prefix", ["x", "=", " \t+"])
@pytest.mark.parametrize("overflow", [False, True], ids=["exact-limit", "one-over"])
def test_optional_text_uses_formatted_cell_budget(tmp_path, suffix, field, prefix, overflow):
    # A name appears with decoration in the calendar, not only in detail.
    calendar_decoration = len("◆  · Persönliche Arbeit\nohne Zeiten")
    limit = 32767 - (calendar_decoration if field == "name" else int(prefix != "x"))
    value = prefix + "x" * (limit - len(prefix) + overflow)
    snapshot = personal_snapshot({**GOOD_LABELS, field: value})
    expected = {**GOOD_LABELS, field: value if not overflow else "Persönliche Arbeit" if field == "name" else ""}
    rows, calendar, balances = read_export(tmp_path, snapshot, suffix)
    assert_personal_readback(rows, calendar, balances, snapshot, suffix, expected)


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
@pytest.mark.parametrize("value", ["\t=literal\n", "  first\nsecond\tlast  "])
@pytest.mark.parametrize("field", FIELDS)
def test_optional_portable_whitespace_is_preserved_not_stripped(tmp_path, suffix, field, value):
    snapshot = personal_snapshot({**GOOD_LABELS, field: value})
    rows, calendar, balances = read_export(tmp_path, snapshot, suffix)
    assert_personal_readback(rows, calendar, balances, snapshot, suffix, {**GOOD_LABELS, field: value})


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
@pytest.mark.parametrize("shape", ["split", "separate-works"])
def test_optional_name_budget_includes_repeated_calendar_labels(tmp_path, suffix, shape):
    snapshot = personal_snapshot({**GOOD_LABELS, "name": "x" * 20000})
    if shape == "split":
        work = snapshot.boundary_work[0]
        work.day, work.in_period, work.kind = None, True, "day"
        start = datetime(2026, 1, 5, 8, tzinfo=UTC)
        work.segments = [Interval(start=start, end=start + timedelta(hours=1)),
                         Interval(start=start + timedelta(hours=2), end=start + timedelta(hours=3))]
    else:
        snapshot.boundary_work.append(snapshot.boundary_work[0].model_copy(update={"id": "second exact ID", "paid_minutes": 0}))
        snapshot.metadata["provenance"]["second exact ID"] = {"name": "y" * 20000}
    snapshot = Snapshot.model_validate(snapshot.model_dump())
    rows, calendar, _ = read_export(tmp_path, snapshot, suffix)
    details = [r for r in rows if len(r) >= 12 and r[2] in {WORK_ID, "second exact ID"}]
    expected_names = ["Persönliche Arbeit", "Persönliche Arbeit"] if shape == "split" else ["x" * 20000, "Persönliche Arbeit"]
    assert [r[5] for r in details] == expected_names
    assert sum(int(r[8]) for r in details if r[8] not in (None, "")) == 120
    if calendar is not None:
        assert len(calendar["B5"]) <= 32767
        assert calendar["B5"].count("Persönliche Arbeit") == 2


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
def test_optional_name_never_displaces_mandatory_staffing_text(tmp_path, suffix):
    snapshot = personal_snapshot(GOOD_LABELS)
    staffed = snapshot_for_review(days=1)
    snapshot.shifts, snapshot.demands = staffed.shifts, staffed.demands
    snapshot.profiles[0].min_rest_minutes = 0
    work = snapshot.boundary_work[0]
    work.day, work.in_period, work.kind = None, True, "day"
    work.segments = [Interval(start=datetime(2026, 1, 5, 18, tzinfo=UTC),
                              end=datetime(2026, 1, 5, 20, tzinfo=UTC))]
    decoration = len(" · Synthetic role\n08:00–16:00\n\n◆ Persönliche Arbeit\n18:00–20:00")
    # One byte is reserved for existing formula protection of the first title.
    name = "=" + "x" * (32767 - decoration - 2)
    snapshot.shifts[0].name = name
    snapshot = Snapshot.model_validate_json(snapshot.model_dump_json())
    plan = [Assignment(employee_id="candidate", demand_id=snapshot.demands[0].id)]
    rows, calendar, balances = read_export(tmp_path, snapshot, suffix, plan)
    references = {snapshot.demands[0].id, WORK_ID}
    details = [r for r in rows if len(r) >= 12 and r[2] in references]
    assert [r[2] for r in details] == [snapshot.demands[0].id, WORK_ID]
    assert [r[5] for r in details] == ["'" + name, "Persönliche Arbeit"]
    assert sum(int(r[8]) for r in details) == 600
    if calendar is not None:
        assert len(calendar["B5"]) == 32767
        assert calendar["B5"].startswith("'" + name)
        assert balances["C5"] == 10
        assert balances["F5"] == 7.25


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
@pytest.mark.parametrize("label", ["x" * 32767, "=source\u00a0 λ "], ids=["max-plain", "formula-unicode"])
def test_context_only_label_keeps_exact_text_and_zero_period_credit(tmp_path, suffix, label):
    snapshot = personal_snapshot({**GOOD_LABELS, "name": label})
    work = snapshot.boundary_work[0]
    work.day, work.kind = None, "day"
    work.segments = [Interval(start=datetime(2026, 1, 4, 8, tzinfo=UTC),
                              end=datetime(2026, 1, 4, 10, tzinfo=UTC))]
    snapshot = Snapshot.model_validate_json(snapshot.model_dump_json())
    rows, calendar, balances = read_export(tmp_path, snapshot, suffix)
    detail = next(r for r in rows if len(r) >= 12 and r[2] == WORK_ID)
    assert detail[5] == protected(label)
    assert detail[10] == "Randdienst"
    assert int(detail[8]) == 120
    if calendar is not None:
        assert calendar["B5"] is None
        assert balances["C5"] == 0
    entry, = export_work(snapshot, [])
    assert entry.work is snapshot.boundary_work[0]
    assert entry.period_paid_minutes == 0


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
@pytest.mark.parametrize("days", [1, 2])
def test_name_budget_accounts_for_overnight_decorations_without_losing_credit(tmp_path, suffix, days):
    snapshot = personal_snapshot(GOOD_LABELS)
    snapshot.period_end += timedelta(days=days)

    work = snapshot.boundary_work[0]
    start = datetime(2026, 1, 5, 23, tzinfo=UTC)
    end = datetime(2026, 1, 5, tzinfo=UTC) + timedelta(days=days)
    work.segments = [Interval(start=start, end=end)]
    work.day, work.kind, work.in_period = None, "night", True
    label = "λ" * (32767 - len(f"◆  · Persönliche Arbeit\n23:00–00:00 (+{days})"))
    snapshot.metadata["provenance"][WORK_ID]["name"] = label
    snapshot = Snapshot.model_validate_json(snapshot.model_dump_json())
    rows, calendar, balances = read_export(tmp_path, snapshot, suffix)
    detail = next(r for r in rows if len(r) >= 12 and r[2] == WORK_ID)
    assert detail[5] == label
    assert int(detail[8]) == 120
    if calendar is not None:
        for column in ("B", "C") if days == 1 else ("B", "C", "D"):
            # Exact-midnight end is excluded: only the first 'days' cells exist.
            if column < chr(ord("B") + days):
                assert len(calendar[column + "5"]) == 32767
            else:
                assert calendar[column + "5"] is None
        assert balances["C5"] == 2
