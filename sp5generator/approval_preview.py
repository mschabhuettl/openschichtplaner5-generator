"""What a single missing approval would make possible - without granting one.

An approval is a qualification decision and stays with the planning office; this
module never creates, suggests or ranks people. It answers the question that
otherwise costs a full recomputation per attempt: which duties would become
staffable at all, and whose unreachable target would come within reach.

Nothing here changes the project. The figures describe possibility, not a plan:
whether the search actually moves work depends on every other rule as well.
"""
from .domain import eligibility


def approval_leverage(snapshot, assignments, limit=50):
    """Per person and duty type: what granting that one approval would open up."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
        raise ValueError("Die Zahl der gezeigten Zeilen muss zwischen 1 und 1000 liegen.")
    shifts = {s.id: s for s in snapshot.shifts}
    positions = {p.id: p for p in snapshot.positions}
    demands = [d for d in snapshot.demands if d.minimum > 0]
    planable = [e for e in snapshot.employees if not e.excluded]

    all_demands = {d.id: d for d in snapshot.demands}
    worked = dict.fromkeys((e.id for e in planable), 0)
    for assignment in assignments:
        demand = all_demands.get(assignment.demand_id)
        if demand is not None and assignment.employee_id in worked:
            worked[assignment.employee_id] += shifts[demand.shift_id].paid_minutes

    # Ein Bedarf, für den heute niemand freigegeben ist, bleibt unbesetzbar -
    # dort zählt eine Freigabe doppelt: sie schließt eine Lücke, statt nur Last
    # zu verschieben.
    covered = {
        d.id: any(not eligibility(snapshot, e, d) for e in planable) for d in demands
    }
    shortfall = {
        e.id: max(0, e.target_minutes - worked[e.id]) for e in planable if e.target_minutes
    }

    rows = {}
    for person in planable:
        granted = {a.function_id for a in person.approvals}
        for demand in demands:
            function = positions[demand.position_id].function_id
            if function in granted:
                continue
            # Nur wo die Freigabe die einzige Hürde ist, ändert sie etwas.
            if set(eligibility(snapshot, person, demand)) - {"approval"}:
                continue
            row = rows.setdefault((person.id, function), {
                "employee_id": person.id, "function_id": function,
                "reachable_demands": 0, "reachable_minutes": 0,
                "unstaffable_demands": 0,
            })
            row["reachable_demands"] += 1
            row["reachable_minutes"] += shifts[demand.shift_id].paid_minutes
            if not covered[demand.id]:
                row["unstaffable_demands"] += 1

    for (eid, _), row in rows.items():
        row["own_shortfall_minutes"] = shortfall.get(eid, 0)
        # Mehr als das eigene Soll bringt der Person nichts; für die Deckung
        # zählt die Stelle trotzdem, deshalb bleibt beides getrennt ausgewiesen.
        row["usable_minutes"] = min(row["reachable_minutes"], shortfall.get(eid, 0))

    ranked = sorted(
        rows.values(),
        key=lambda row: (-row["unstaffable_demands"], -row["usable_minutes"],
                         -row["reachable_minutes"], row["employee_id"], row["function_id"]),
    )
    # Je Dienstart zusammengefasst: dieselbe fehlende Freigabe trifft meist
    # dutzende Personen, und eine Liste je Person ist dann keine Arbeitsliste.
    services = {}
    for row in ranked:
        entry = services.setdefault(row["function_id"], {
            "function_id": row["function_id"], "people": 0,
            "unstaffable_demands": 0, "best_usable_minutes": 0,
        })
        entry["people"] += 1
        entry["unstaffable_demands"] = max(
            entry["unstaffable_demands"], row["unstaffable_demands"]
        )
        entry["best_usable_minutes"] = max(
            entry["best_usable_minutes"], row["usable_minutes"]
        )
    return {
        "candidates": len(ranked),
        "services": sorted(
            services.values(),
            key=lambda entry: (-entry["unstaffable_demands"],
                               -entry["best_usable_minutes"], entry["function_id"]),
        ),
        "unstaffable_demands": sum(1 for d in demands if not covered[d.id]),
        "people_below_target": sum(1 for value in shortfall.values() if value > 0),
        "shortfall_minutes": sum(shortfall.values()),
        "rows": ranked[:limit],
    }
