"""Explicitly selected history-based service approvals; no inferred qualifications."""
from .models import Approval


def apply_history_approvals(snapshot, minimum_days=3):
    if isinstance(minimum_days, bool) or not isinstance(minimum_days, int) or not 2 <= minimum_days <= 1097:
        raise ValueError("Mindestens 2 bis höchstens 1097 unterschiedliche Einsatztage wählen.")
    people = {e.id: e for e in snapshot.employees}
    applied = []
    for row in snapshot.metadata.get("history_matrix", []):
        employee = people.get(row.get("employee_id"))
        if employee is None:
            continue
        for candidate in row.get("suggested_approvals", []):
            days = candidate.get("evidence_days", 0)
            function = candidate.get("function_id")
            if not function or not isinstance(days, int) or days < minimum_days:
                continue
            # Existing individual/supervised approvals must never be widened.
            if any(a.function_id == function for a in employee.approvals):
                continue
            start = max(snapshot.period_start, employee.employment_start)
            end = min(snapshot.period_end, employee.employment_end)
            if start > end:
                continue
            employee.approvals.append(Approval(function_id=function, workplace_id="*", valid_from=start, valid_until=end))
            applied.append({"employee_id": employee.id, "function_id": function,
                            "evidence_days": days, "valid_from": str(start), "valid_until": str(end)})
    snapshot.metadata["history_automation"] = {
        "mode": "explicit-history-approval", "minimum_days": minimum_days,
        "applied": applied,
    }
    snapshot.metadata["history_notice"] = (
        "Automatische Dienstfreigaben wurden beim Import ausdrücklich aktiviert. "
        "Die Mindestanzahl zählt unterschiedliche historische Einsatztage. "
        "Freigaben gelten nur im Planungszeitraum und ersetzen keine Qualifikationsnachweise."
    )
    return snapshot
