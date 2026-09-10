from sp5generator.export import safe_cell


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
