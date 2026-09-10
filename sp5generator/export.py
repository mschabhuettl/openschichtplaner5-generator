"""Portable tabular exports with spreadsheet formula protection."""

import csv
from collections import Counter
from pathlib import Path
from .models import Snapshot, Result


def safe_cell(value):
    if isinstance(value, str) and value.lstrip().startswith(
        ("=", "+", "-", "@", "\t", "\r", "\n")
    ):
        return "'" + value
    return value


def vacancy_counts(snapshot: Snapshot, assignments):
    """Derive staffing gaps from current assignments, never cached solver output."""
    employee_ids = {employee.id for employee in snapshot.employees}
    counts = Counter(
        demand_id
        for employee_id, demand_id in {
            (assignment.employee_id, assignment.demand_id)
            for assignment in assignments
            if assignment.employee_id in employee_ids
        }
    )
    return {
        demand.id: max(0, demand.minimum - counts[demand.id])
        for demand in snapshot.demands
    }


def rows(snapshot: Snapshot, result: Result):
    yield ["Zeitraum", str(snapshot.period_start), str(snapshot.period_end)]
    yield [
        "Status",
        result.solver_status,
        "Vollständig" if result.validation.complete else "Nicht vollständig",
    ]
    yield [
        "Person-ID",
        "Person",
        "Bedarf",
        "Funktion",
        "Arbeitsplatz",
        "Dienst",
        "Beginn",
        "Ende",
        "Gutschrift Minuten",
        "Fixiert",
    ]
    people = {e.id: e for e in snapshot.employees}
    demands = {d.id: d for d in snapshot.demands}
    shifts = {s.id: s for s in snapshot.shifts}
    positions = {p.id: p for p in snapshot.positions}
    worked = {e.id: 0 for e in snapshot.employees}
    for a in result.assignments:
        d = demands[a.demand_id]
        s, p = shifts[d.shift_id], positions[d.position_id]
        from .timeutils import bounds, local_day

        day = local_day(bounds(s)[0], snapshot.timezone)
        if snapshot.period_start <= day <= snapshot.period_end:
            worked[a.employee_id] += s.paid_minutes
        for i, interval in enumerate(s.segments):
            yield [
                a.employee_id,
                people[a.employee_id].name,
                d.id,
                p.function_id,
                p.workplace_id,
                s.name,
                interval.start.isoformat(),
                interval.end.isoformat(),
                s.paid_minutes if i == 0 else "",
                a.fixed,
            ]
    yield []
    yield [
        "Person-ID",
        "Soll Minuten",
        "Ist einschließlich Gutschrift Minuten",
        "Saldo Minuten",
    ]
    for e in snapshot.employees:
        actual = worked[e.id] + e.credit_minutes
        yield [
            e.id,
            e.target_minutes,
            actual,
            actual + e.balance_minutes - e.target_minutes,
        ]
    yield []
    yield ["Offener Bedarf", "Anzahl", "Dienst", "Funktion", "Arbeitsplatz"]
    for did, n in vacancy_counts(snapshot, result.assignments).items():
        if n:
            d = demands[did]
            p = positions[d.position_id]
            yield [did, n, shifts[d.shift_id].name, p.function_id, p.workplace_id]
    if result.validation.diagnostics:
        yield []
        yield ["Prüfhinweis", "Meldung", "Person-ID", "Bedarf", "Datum"]
        for diagnostic in result.validation.diagnostics:
            yield [diagnostic.code, diagnostic.message, diagnostic.employee_id or "",
                   diagnostic.demand_id or "", diagnostic.date or ""]


def export_table(snapshot: Snapshot, result: Result, path: str | Path):
    from .domain import snapshot_hash
    from .validator import validate

    if result.snapshot_id != snapshot.id or result.snapshot_hash != snapshot_hash(snapshot):
        raise ValueError("Result does not reference this snapshot")
    validation = validate(snapshot, result.assignments)
    if not validation.valid:
        raise ValueError("Ungültigen Entwurf zuerst korrigieren; Export wurde nicht erstellt.")
    result = result.model_copy(update={"validation": validation})
    path = Path(path)
    if path.suffix.lower() == ".xlsx":
        from .workbook import planning_workbook

        planning_workbook(snapshot, result).save(path)
    elif path.suffix.lower() == ".csv":
        with path.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.writer(output)
            for row in rows(snapshot, result):
                writer.writerow([safe_cell(v) for v in row])
    else:
        raise ValueError("Export requires .csv or .xlsx")
