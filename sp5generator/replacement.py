"""Who can step in for an absent person, and who has waited longest for a duty.

The search answers a phone call, not a plan: it never changes assignments. It
applies the same hard rules the planner applies - approval, employment, team,
duty kind, availability, absence, rest and overlap - and then sorts the people
who remain by how long they have been without a duty.
"""
from datetime import date

from .domain import eligibility, pair_conflict
from .models import Shift
from .timeutils import bounds, local_day


def _day(shift, zone):
    return local_day(bounds(shift)[0], zone)


def _duty_shifts(snapshot, assignments):
    """Every duty a person holds, from the draft plan and from fixed context work."""
    demands = {d.id: d for d in snapshot.demands}
    shifts = {s.id: s for s in snapshot.shifts}
    held = {}
    for assignment in assignments:
        demand = demands.get(assignment.demand_id)
        shift = shifts.get(demand.shift_id) if demand else None
        if shift is not None:
            held.setdefault(assignment.employee_id, []).append(shift)
    for work in snapshot.boundary_work:
        held.setdefault(work.employee_id, []).append(Shift(
            id=work.id, name="Randdienst", kind=work.kind if work.kind != "unknown" else "day",
            team_id="", segments=work.segments, paid_minutes=0, source="boundary",
        ))
    return held


def replacement_candidates(snapshot, assignments, employee_id, absent_from, absent_until):
    """Ranked stand-ins per freed duty, plus who could cover the whole absence."""
    if not isinstance(absent_from, date) or not isinstance(absent_until, date):
        raise ValueError("Abwesenheit braucht ein Anfangs- und ein Enddatum.")
    if absent_until < absent_from:
        raise ValueError("Die Abwesenheit endet vor ihrem Beginn.")
    people = {e.id: e for e in snapshot.employees}
    if employee_id not in people:
        raise ValueError("Die abwesende Person gehört nicht zu diesem Projekt.")
    demands = {d.id: d for d in snapshot.demands}
    shifts = {s.id: s for s in snapshot.shifts}
    zone = snapshot.timezone
    held = _duty_shifts(snapshot, assignments)

    freed = [
        a for a in assignments
        if a.employee_id == employee_id and a.demand_id in demands
        and absent_from <= _day(shifts[demands[a.demand_id].shift_id], zone) <= absent_until
    ]
    freed.sort(key=lambda a: (_day(shifts[demands[a.demand_id].shift_id], zone), a.demand_id))

    def waited(person):
        """Days since the person's last duty before the absence; None if never."""
        days = [_day(s, zone) for s in held.get(person.id, [])
                if _day(s, zone) < absent_from]
        return (absent_from - max(days)).days if days else None

    duties, everywhere = [], None
    for assignment in freed:
        demand = demands[assignment.demand_id]
        shift = shifts[demand.shift_id]
        taken = {a.employee_id for a in assignments if a.demand_id == demand.id}
        blocked, ranked = {}, []
        for person in snapshot.employees:
            if person.id == employee_id:
                continue
            reasons = eligibility(snapshot, person, demand)
            if person.id in taken:
                reasons = [*reasons, "already_on_duty"]
            conflict = next(
                (c for other in held.get(person.id, [])
                 if (c := pair_conflict(snapshot, person, other, shift))),
                None,
            ) if not reasons else None
            if conflict:
                reasons = [conflict]
            if reasons:
                for reason in reasons:
                    blocked[reason] = blocked.get(reason, 0) + 1
                continue
            ranked.append(person.id)
        waiting = {pid: waited(people[pid]) for pid in ranked}
        # Longest wait first; someone never on duty in this window waits longest.
        ranked.sort(key=lambda pid: (-(waiting[pid] if waiting[pid] is not None else 10**6), pid))
        duties.append({
            "demand_id": demand.id, "shift_id": shift.id, "shift_name": shift.name,
            "date": str(_day(shift, zone)),
            "candidates": [{"employee_id": pid, "days_since_last_duty": waiting[pid]}
                           for pid in ranked],
            "blocked": dict(sorted(blocked.items())),
        })
        everywhere = set(ranked) if everywhere is None else everywhere & set(ranked)

    return {
        "employee_id": employee_id,
        "absent_from": str(absent_from), "absent_until": str(absent_until),
        "duties": duties,
        "covers_whole_absence": sorted(everywhere or ()),
    }
