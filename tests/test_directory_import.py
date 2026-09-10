"""Historical suggestions use only newly constructed source records."""

from datetime import date
import pytest

pytest.importorskip("sp5lib")
from sp5generator import sp5_adapter as adapter
from test_sp5_adapter import SyntheticDatabase
from test_sp5_dbf import empty_table


class HistorySource(SyntheticDatabase):
    def get_groups(self):
        return [{"ID": 1, "NAME": "Team A"}]

    def get_schedule(self, year, month, **kwargs):
        if (year, month) != (2026, 1):
            return []
        return [
            {
                "employee_id": 101,
                "date": "2026-01-02",
                "kind": "shift",
                "shift_id": 201,
                "workplace_id": 301,
            },
            {
                "employee_id": 101,
                "date": "2026-01-03",
                "kind": "shift",
                "shift_id": 201,
                "workplace_id": 301,
            },
            {
                "employee_id": 101,
                "date": "2026-01-03",
                "kind": "shift",
                "shift_id": 201,
                "workplace_id": 301,
            },
            {
                "employee_id": 101,
                "date": "2026-01-04",
                "kind": "absence",
                "shift_id": 201,
                "workplace_id": 301,
            },
        ]


def test_history_is_an_editable_proposal_not_qualification():
    db = HistorySource()
    snapshot = adapter.import_snapshot(
        db, date(2026, 1, 6), date(2026, 1, 6), "1", "UTC"
    )
    matrix = adapter.historical_matrix(db, snapshot, date(2026, 1, 1), date(2026, 1, 5))
    assert matrix[0]["observed_assignment_count"] == 2
    assert matrix[0]["observed_shifts"][0]["first_date"] == "2026-01-02"
    assert matrix[0]["observed_shifts"][0]["last_date"] == "2026-01-03"
    suggestion = matrix[0]["suggested_approvals"][0]
    assert suggestion["evidence_count"] == 2 and suggestion["confirmed"] is False
    assert suggestion["workplace_id"] == "sp5:workplace:301"
    assert snapshot.employees[0].approvals == []
    assert snapshot.employees[0].qualifications == []


def test_directory_accepts_one_child_and_case_insensitive_tables(tmp_path):
    folder = tmp_path / "Database"
    folder.mkdir()
    for name in ["empl", "group", "grasg", "shift", "wopl"]:
        empty_table(folder / f"5{name}.dbf", [("ID", "N", 8)])
    result = adapter.inspect_directory(str(tmp_path))
    assert result["directory"] == str(folder)
    assert result["source_read_only"]
    assert "5EMPL.DBF" in result["files"]
    empty_table(tmp_path / "5EMPL.DBF", [("ID", "N", 8)])
    assert adapter.inspect_directory(str(tmp_path))["directory"] == str(folder)


def test_directory_rejects_source_escape_and_ambiguous_roots(tmp_path, monkeypatch):
    monkeypatch.setenv("SP5_SOURCE_ROOT", str(tmp_path / "allowed"))
    (tmp_path / "allowed").mkdir()
    with pytest.raises(ValueError):
        adapter.inspect_directory(str(tmp_path))
    monkeypatch.delenv("SP5_SOURCE_ROOT")
    for sub in ["one", "two"]:
        folder = tmp_path / sub
        folder.mkdir()
        for name in ["EMPL", "GROUP", "GRASG", "SHIFT", "WOPL"]:
            empty_table(folder / f"5{name}.DBF", [("ID", "N", 8)])
    with pytest.raises(ValueError):
        adapter.inspect_directory(str(tmp_path))


def test_import_detects_concurrent_change_and_keeps_source_readonly(
    tmp_path, monkeypatch
):
    marker = tmp_path / "5EMPL.DBF"
    marker.write_bytes(b"synthetic")
    db = HistorySource()
    monkeypatch.setattr(
        adapter, "_source_database", lambda directory: (db, {"5EMPL.DBF": marker})
    )
    snapshot = adapter.import_directory(
        str(tmp_path),
        date(2026, 1, 6),
        date(2026, 1, 6),
        "1",
        "UTC",
        date(2026, 1, 1),
        date(2026, 1, 5),
    )
    assert snapshot.metadata["history_matrix"][0]["observed_assignment_count"] == 2
    assert marker.read_bytes() == b"synthetic"
    original = adapter.historical_matrix

    def changed(*args):
        result = original(*args)
        marker.write_bytes(b"synthetic changed")
        return result

    monkeypatch.setattr(adapter, "historical_matrix", changed)
    with pytest.raises(ValueError, match="verändert"):
        adapter.import_directory(
            str(tmp_path),
            date(2026, 1, 6),
            date(2026, 1, 6),
            "1",
            "UTC",
            date(2026, 1, 1),
            date(2026, 1, 5),
        )
