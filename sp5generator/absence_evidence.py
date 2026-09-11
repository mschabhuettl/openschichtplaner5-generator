"""Dated source-account evidence, never an automatic replanning credit."""

from dataclasses import asdict
import math


def absence_evidence(db, employees, schedule, start, end, holidays):
    """Evaluate visible, deduplicated schedule rows with the existing SP5 library.

    Schedule does not expose ABSEN record IDs; these are not certified account
    totals. Missing definitions must not become the library's silent zero.
    """
    from sp5lib import calculations as calc

    contexts = {e["ID"]: calc.EmployeeContext.from_record(e) for e in employees}
    result = {eid: {
        "table": "ABSEN", "plan": "ist", "applied": False,
        "period_start": start.isoformat(), "period_end": end.isoformat(),
        "source": "deduplicated_schedule_without_absen_ids",
        "rows": [],
    } for eid in contexts}
    selected = [r for r in schedule if r.get("kind") == "absence"
                and r.get("employee_id") in contexts
                and start <= calc.to_date(r.get("date")) <= end]
    definitions = ({r["ID"]: r for r in db.get_leave_types(include_hidden=True)}
                   if selected and hasattr(db, "get_leave_types") else {})
    for row in selected:
        day = calc.to_date(row["date"])
        type_id = row.get("leave_type_id")
        evidence = {"date": day.isoformat(), "leave_type_id": type_id,
                    "interval": row.get("interval"), "status": "unresolved"}
        result[row["employee_id"]]["rows"].append(evidence)
        definition = definitions.get(type_id) if type_id is not None else None
        if definition is None:
            evidence["reason"] = "missing_leave_type_definition"
            continue
        interval = row.get("interval")
        if interval not in (0, 1, 2, 3):
            evidence["reason"] = "invalid_interval"
            continue
        record = {"DATE": day, "LEAVETYPID": type_id, "INTERVAL": interval}
        if interval == 3:
            try:
                a, b = int(str(row.get("start_time"))), int(str(row.get("end_time")))
            except (TypeError, ValueError):
                a = b = -1
            if not (0 <= a < 1440 and 0 <= b <= 1440 and a != b):
                evidence["reason"] = "invalid_interval"
                continue
            record.update(START=a, END=b)
            evidence.update(start_time=a, end_time=b)
        context = contexts[row["employee_id"]]
        sums = asdict(calc.absence_sums(
            context, day, day, holidays=holidays, absences=[record],
            leave_types_by_id={type_id: definition},
        ))
        if not all(math.isfinite(value) for value in sums.values()):
            raise ValueError("Abwesenheitsbewertung enthält ungültige Stundenwerte.")
        evidence.update(
            status="evaluated", hours=sums,
            definition={k: definition.get(k) for k in (
                "COUNTALL", "CHARGETYP", "CHARGEHRS", "DEDUCTACT", "DEDUCTOVT",
            )},
        )
    return result
