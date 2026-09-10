from sp5generator.export import safe_cell
import csv

import pytest


def test_spreadsheet_formulas_are_escaped():
    for text in ["=1+1", " +2", "-3", "@SUM(A1:A2)", "\t=1", "\r=1"]:
        assert safe_cell(text).startswith("'")
    assert safe_cell("Testperson 001") == "Testperson 001"
    assert safe_cell(-23) == -23


def test_context_duty_does_not_change_period_balance():
    from datetime import timedelta
    from sp5generator.demo import make_demo
    from sp5generator.models import Assignment, Result, Validation
    from sp5generator.export import rows

    snapshot = make_demo(days=1)
    shift = snapshot.shifts[0]
    shift.segments = [
        i.model_copy(
            update={
                "start": i.start - timedelta(days=2),
                "end": i.end - timedelta(days=2),
            }
        )
        for i in shift.segments
    ]
    result = Result(
        snapshot_id=snapshot.id,
        snapshot_hash="unused",
        solver_status="FEASIBLE",
        assignments=[Assignment(employee_id="e000", demand_id="d0-day-p0")],
        validation=Validation(valid=True, complete=False, diagnostics=[]),
        runtime_seconds=0,
    )
    output = list(rows(snapshot, result))
    balance = next(row for row in output if len(row) == 4 and row[0] == "e000")
    assert balance[2] == snapshot.employees[0].credit_minutes


def incomplete_result(snapshot):
    from sp5generator.domain import snapshot_hash
    from sp5generator.models import Result, Validation

    return Result(
        snapshot_id=snapshot.id,
        snapshot_hash=snapshot_hash(snapshot),
        solver_status="FEASIBLE",
        vacancies={"stale-demand": 99},
        validation=Validation(valid=True, complete=True, diagnostics=[]),
        runtime_seconds=0,
    )


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
def test_partial_export_revalidates_and_recomputes_vacancies(tmp_path, suffix):
    from sp5generator.demo import make_demo
    from sp5generator.export import export_table

    snapshot = make_demo(days=1)
    snapshot.assignments = []
    result = incomplete_result(snapshot)
    target = tmp_path / f"partial.{suffix}"
    export_table(snapshot, result, target)
    if suffix == "csv":
        with target.open(encoding="utf-8-sig", newline="") as stream:
            output = list(csv.reader(stream))
    else:
        from openpyxl import load_workbook
        workbook = load_workbook(target)
        output = list(workbook.active.values)
        workbook.close()
    assert output[1][2] == "Nicht vollständig"
    assert any(row[0] == snapshot.demands[0].id and str(row[1]) == str(snapshot.demands[0].minimum)
               for row in output if row)
    assert any(row[0] == "vacancy" for row in output if row)
    assert all(row[0] != "stale-demand" for row in output if row)


@pytest.mark.parametrize("invalid", ["unknown-person", "duplicate", "interval-mismatch"])
def test_invalid_export_leaves_existing_file_unchanged(tmp_path, invalid):
    from datetime import timedelta
    from sp5generator.demo import make_demo
    from sp5generator.export import export_table
    from sp5generator.models import Assignment

    snapshot = make_demo(days=1)
    result = incomplete_result(snapshot)
    assignment = Assignment(employee_id="e000", demand_id=snapshot.demands[0].id)
    if invalid == "unknown-person":
        assignment.employee_id = "missing"
    if invalid == "interval-mismatch":
        assignment.segments = [segment.model_copy(update={"end": segment.end + timedelta(minutes=1)})
                               for segment in snapshot.shifts[0].segments]
    result.assignments = [assignment, assignment] if invalid == "duplicate" else [assignment]
    target = tmp_path / "plan.csv"
    target.write_bytes(b"previous export")
    with pytest.raises(ValueError, match="Ungültigen Entwurf"):
        export_table(snapshot, result, target)
    assert target.read_bytes() == b"previous export"


def test_export_checks_snapshot_identity(tmp_path):
    from sp5generator.demo import make_demo
    from sp5generator.export import export_table

    snapshot = make_demo(days=1)
    result = incomplete_result(snapshot)
    result.snapshot_id = "another-snapshot"
    with pytest.raises(ValueError, match="reference"):
        export_table(snapshot, result, tmp_path / "plan.csv")
