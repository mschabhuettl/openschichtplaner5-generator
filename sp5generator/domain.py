"""Pure domain predicates and snapshot integrity."""

import hashlib
import json
from collections import deque
from datetime import date, timedelta
from zoneinfo import ZoneInfo
from .models import Diagnostic
from .timeutils import (
    minute,
    local_day,
    availability_window,
    midnight,
    dates,
    segments,
    bounds,
    overlap,
    day_minutes,
)

# Standalone execution budgets, independent of HTTP body limits. The 120-person,
# 31-day benchmark fits comfortably. Import-history ranges are a separate concern.
MAX_PLANNING_DAYS = 366
MAX_CONTEXT_DAYS = 1096
MAX_RECORDS = 50000  # Includes nested approvals, intervals and availability.
MAX_ASSIGNMENTS = 5000
MAX_CANDIDATE_PAIRS = 2_000_000  # Employee x demand model construction.
MAX_LOCAL_REST_WINDOWS = 10_000_000  # Minute anchors across employee profiles.
MAX_CALENDAR_CHECKS = 5_000_000  # Profile scans and availability-day expansion.
COLLECTION_LIMITS = {
    "employees": 1000, "positions": 1000, "shifts": 10000,
    "demands": 20000, "profiles": 1000, "assignments": MAX_ASSIGNMENTS,
    "restrictions": 20000, "wishes": 20000,
}


def snapshot_hash(snapshot):
    return hashlib.sha256(
        json.dumps(
            snapshot.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def maximum_matching(adjacency):
    """Map right vertices to left vertices without a recursion-depth limit."""
    matched = {}
    for root in adjacency:
        parents = {root: None}
        pending = deque([root])
        seen = set()
        augmented = False
        while pending and not augmented:
            left = pending.popleft()
            for right in adjacency[left]:
                if right in seen:
                    continue
                seen.add(right)
                if right in matched:
                    displaced = matched[right]
                    if displaced not in parents:
                        parents[displaced] = (left, right)
                        pending.append(displaced)
                    continue
                # Reverse the alternating path ending at this free slot.
                while True:
                    matched[right] = left
                    previous = parents[left]
                    if previous is None:
                        break
                    left, right = previous
                augmented = True
                break
    return matched


def profiles_for(snapshot, employee, day):
    return [
        p
        for p in snapshot.profiles
        if p.id in employee.profile_ids and p.valid_from <= day <= p.valid_until
    ]


def availability_active(availability, day):
    return (
        availability.valid_from <= day <= availability.valid_until
        and day.weekday() in availability.weekdays
        and (
            availability.cycle_anchor is None
            or ((day - availability.cycle_anchor).days // 7) % availability.cycle_weeks
            == availability.cycle_phase
        )
    )


def eligibility(snapshot, employee, demand):
    shift = next(s for s in snapshot.shifts if s.id == demand.shift_id)
    position = next(p for p in snapshot.positions if p.id == demand.position_id)
    a, b = bounds(shift)
    first, last = local_day(a, snapshot.timezone), local_day(b - 1, snapshot.timezone)
    reasons = []
    if not employee.employment_start <= first <= last <= employee.employment_end:
        reasons.append("employment")
    if shift.team_id not in employee.team_ids:
        reasons.append("team")
    if shift.kind not in employee.allowed_kinds:
        reasons.append("kind")
    if not employee.allow_weekends and any(
        d.weekday() >= 5 for d in day_minutes(shift, snapshot.timezone)
    ):
        reasons.append("weekend")
    if shift.holiday and not employee.allow_holidays:
        reasons.append("holiday")
    approvals = [
        p
        for p in employee.approvals
        if p.function_id == position.function_id
        and p.workplace_id in ("*", position.workplace_id)
        and p.valid_from <= first
        and last <= p.valid_until
    ]
    if not approvals:
        reasons.append("approval")
    if position.qualifications_required:
        if not position.qualification_ids or any(
            not any(
                q.id == required
                and q.valid_from <= first
                and q.valid_until >= last
                and q.level >= position.qualification_level
                for q in employee.qualifications
            )
            for required in position.qualification_ids
        ):
            reasons.append("qualification")
    if any(
        r.employee_id == employee.id
        and r.shift_id == shift.id
        and (r.level == 2 or (r.level == 1 and not r.approved))
        for r in snapshot.restrictions
    ):
        reasons.append("restriction")
    if any(
        overlap(span, (minute(i.start), minute(i.end)))
        for span in segments(shift)
        for i in employee.unavailable
    ):
        reasons.append("absence")
    if employee.availability:
        windows = []
        for day in dates(first - timedelta(days=1), last):
            for v in employee.availability:
                if not availability_active(v, day):
                    continue
                windows.append(availability_window(day, v, snapshot.timezone))
        for start, end in segments(shift):
            cursor = start
            for x, y in sorted(windows):
                if x <= cursor:
                    cursor = max(cursor, y)
            if cursor < end:
                reasons.append("availability")
                break
    return reasons


def supervised(snapshot, employee, demand):
    shift = next(s for s in snapshot.shifts if s.id == demand.shift_id)
    position = next(p for p in snapshot.positions if p.id == demand.position_id)
    first, last = (
        local_day(bounds(shift)[0], snapshot.timezone),
        local_day(bounds(shift)[1] - 1, snapshot.timezone),
    )
    approvals = [
        a
        for a in employee.approvals
        if a.function_id == position.function_id
        and a.workplace_id in ("*", position.workplace_id)
        and a.valid_from <= first
        and last <= a.valid_until
    ]
    return bool(approvals) and all(a.supervised for a in approvals)


def planning_record_count(value):
    """Count records once, including scalar list entries, not their container twice."""
    if isinstance(value, dict):
        return 1 + sum(planning_record_count(v) for v in value.values())
    if isinstance(value, list):
        return sum(planning_record_count(v) if isinstance(v, (dict, list)) else 1 for v in value)
    return 0


def input_diagnostics(snapshot):
    errors = []

    def issue(code, message):
        errors.append(Diagnostic(code=code, message=message))

    planning_days = (snapshot.period_end - snapshot.period_start).days + 1
    context_days = (snapshot.context_end - snapshot.context_start).days + 1
    if not (1 <= planning_days <= MAX_PLANNING_DAYS
            and 1 <= context_days <= MAX_CONTEXT_DAYS):
        issue("size_limit", "Planung ist auf 366 Tage und Kontext auf 1096 Tage begrenzt.")
        return errors
    oversized = False
    labels = {"employees": "Personen", "positions": "Positionen", "shifts": "Dienste",
              "demands": "Bedarfe", "profiles": "Regelprofile", "assignments": "Einteilungen",
              "restrictions": "Dienstsperren", "wishes": "Wünsche"}
    for key, limit in COLLECTION_LIMITS.items():
        if len(getattr(snapshot, key)) > limit:
            issue("size_limit", f"Zu viele {labels[key]}; unterstützt sind höchstens {limit}. "
                  "Planungszeitraum oder Teamauswahl verkleinern.")
            oversized = True
    if len(snapshot.employees) * len(snapshot.demands) > MAX_CANDIDATE_PAIRS:
        issue("size_limit", "Zu viele Personen-Bedarf-Kombinationen für einen Rechenlauf "
              "(höchstens 2000000). Kürzeren Planungszeitraum oder weniger Teams wählen.")
        oversized = True
    if sum(d.minimum for d in snapshot.demands) > MAX_ASSIGNMENTS:
        issue("size_limit", "Der Mindestbedarf erfordert mehr als 5000 Einteilungen. "
              "Kürzeren Planungszeitraum oder weniger Teams wählen.")
        oversized = True
    if oversized:
        return errors

    payload = snapshot.model_dump(exclude={"metadata"})
    if planning_record_count(payload) > MAX_RECORDS:
        issue("size_limit", "Zu viele verschachtelte Planungsdatensätze.")
        return errors

    calendar_checks = len(snapshot.employees) * planning_days * len(snapshot.profiles)
    calendar_checks += sum(max(0, (
        min(v.valid_until, snapshot.context_end)
        - max(v.valid_from, snapshot.context_start)
    ).days + 1) for e in snapshot.employees for v in e.availability)
    if calendar_checks > MAX_CALENDAR_CHECKS:
        issue("size_limit", "Zu viele Profil- und Verfügbarkeitsprüfungen; Planung aufteilen.")
        return errors
    local_profiles = {p.id: p for p in snapshot.profiles
                      if p.weekly_rest_minutes and p.weekly_rest_frame == "rolling_local"}
    local_windows = sum(
        (planning_days + local_profiles[pid].weekly_rest_window_days) * 1440
        for employee in snapshot.employees for pid in employee.profile_ids
        if pid in local_profiles
    )
    if local_windows > MAX_LOCAL_REST_WINDOWS:
        issue("size_limit", "Zu viele minutengenaue lokale Wochenruhefenster; Planung aufteilen.")
        return errors

    # CP-SAT accepts bounded machine integers, whereas the JSON contract uses
    # Python integers. Reject unsupported values before constructing expressions.
    def numeric_bounds(value):
        if isinstance(value, dict):
            return all(numeric_bounds(v) for k, v in value.items() if k != "metadata")
        if isinstance(value, list):
            return all(numeric_bounds(v) for v in value)
        return not isinstance(value, int) or abs(value) <= 2**31 - 1

    if not numeric_bounds(payload):
        issue("numeric_range", "Numerische Planungswerte überschreiten den unterstützten Bereich.")
        return errors

    try:
        ZoneInfo(snapshot.timezone)
        # All temporal checks need at least the next local midnight, and rest
        # checks inspect a rule-dependent margin on both sides of the period.
        horizon = max([1] + [max(
            (max(p.min_rest_minutes, p.after_night_rest_minutes,
                 p.after_night_block_rest_minutes) + 1439) // 1440,
            p.max_consecutive_work_days or 0, p.max_consecutive_nights or 0,
            p.weekly_rest_window_days if p.weekly_rest_minutes else 0,
            7 if p.max_weekly_minutes is not None else 0,
        ) for p in snapshot.profiles])
        if (snapshot.context_start == date.min or snapshot.context_end == date.max
                or (snapshot.period_start - date.min).days < horizon
                or (date.max - snapshot.period_end).days <= horizon):
            issue("date_range", "Planungszeitraum und Regelkontext liegen außerhalb des unterstützten Datumsbereichs.")
            return errors
        if (
            not snapshot.context_start
            <= snapshot.period_start
            <= snapshot.period_end
            <= snapshot.context_end
        ):
            issue(
                "period", "Planungszeitraum muss innerhalb des Kontextzeitraums liegen."
            )
        if (
            snapshot.created_at.tzinfo is None
            or snapshot.created_at.utcoffset() is None
        ):
            issue("created_at", "Datenstand benötigt expliziten UTC-Offset.")
        for collection in ("employees", "positions", "shifts", "demands", "profiles"):
            ids = [x.id for x in getattr(snapshot, collection)]
            if any(not id.strip() for id in ids):
                issue("empty_id", "Leere ID in " + collection)
            if len(ids) != len(set(ids)):
                issue("duplicate_id", "Doppelte ID in " + collection)
        shift_ids = {s.id for s in snapshot.shifts}
        position_ids = {p.id for p in snapshot.positions}
        employee_ids = {e.id for e in snapshot.employees}
        demand_ids = {d.id for d in snapshot.demands}
        profile_ids = {p.id for p in snapshot.profiles}
        for s in snapshot.shifts:
            spans = segments(s)
            if (
                not spans
                or any(a >= b for a, b in spans)
                or any(overlap(x, y) for x, y in zip(spans, spans[1:]))
            ):
                issue("interval", "Ungültige oder überlappende Dienstteile: " + s.id)
                continue
            if spans[0][0] < midnight(
                snapshot.context_start, snapshot.timezone
            ) or spans[-1][1] > midnight(
                snapshot.context_end + timedelta(days=1), snapshot.timezone
            ):
                issue("context", "Dienst außerhalb des Kontextzeitraums: " + s.id)
        for d in snapshot.demands:
            if (
                d.shift_id not in shift_ids
                or d.position_id not in position_ids
                or (d.maximum is not None and d.minimum > d.maximum)
            ):
                issue("demand", "Ungültige Bedarfsreferenz oder MIN > MAX: " + d.id)
        for p in snapshot.profiles:
            if p.valid_from > p.valid_until:
                issue("profile", "Ungültiger Profilzeitraum: " + p.id)
        for e in snapshot.employees:
            if e.employment_start > e.employment_end:
                issue("employment", "Ungültiger Beschäftigungszeitraum: " + e.id)
            for record in [*e.approvals, *e.qualifications, *e.availability]:
                if record.valid_from > record.valid_until:
                    issue("validity", "Ungültiger Gültigkeitszeitraum: " + e.id)
            if not e.profile_ids or not set(e.profile_ids) <= profile_ids:
                issue("profile", "Fehlendes Regelprofil: " + e.id)
            for day in dates(snapshot.period_start, snapshot.period_end):
                ps = profiles_for(snapshot, e, day)
                if not ps or any(not p.confirmed for p in ps):
                    issue("profile", "Kein bestätigtes gültiges Regelprofil: " + e.id)
                    break
            for v in e.availability:
                if any(day not in range(7) for day in v.weekdays):
                    issue("availability", "Ungültiger Wochentag: " + e.id)
                if v.cycle_phase >= v.cycle_weeks or (
                    v.cycle_weeks > 1 and v.cycle_anchor is None
                ):
                    issue("availability", "Ungültige Wochenphase: " + e.id)
                for day in dates(
                    max(v.valid_from, snapshot.context_start - timedelta(days=1)),
                    min(v.valid_until, snapshot.context_end),
                ):
                    if availability_active(v, day):
                        availability_window(day, v, snapshot.timezone)
            for i in e.unavailable:
                if minute(i.start) >= minute(i.end):
                    issue("absence", "Ungültige Abwesenheit: " + e.id)
        for a in snapshot.assignments:
            if a.employee_id not in employee_ids or a.demand_id not in demand_ids:
                issue("assignment_reference", "Unbekannte Einteilungsreferenz.")
        for r in [*snapshot.restrictions, *snapshot.wishes]:
            if r.employee_id not in employee_ids or r.shift_id not in shift_ids:
                issue("reference", "Unbekannte Personen- oder Dienstreferenz.")
        for item in snapshot.unresolved:
            issue("unresolved", item)
    except OverflowError:
        issue("date_range", "Datum oder Zeitspanne liegt außerhalb des unterstützten Bereichs.")
    except (ValueError, KeyError) as exc:
        issue("input", str(exc))
    return errors


def pair_conflict(snapshot, employee, left, right):
    ls, rs = segments(left), segments(right)
    if any(overlap(a, b) for a in ls for b in rs):
        return "overlap"
    la, lb = bounds(left)
    ra, rb = bounds(right)
    if ra < la:
        return pair_conflict(snapshot, employee, right, left)
    # A split duty is one duty: interleaving separate duties is incompatible.
    if ra < lb:
        return "interleaving"
    ps = profiles_for(
        snapshot, employee, local_day(ra, snapshot.timezone)
    ) + profiles_for(snapshot, employee, local_day(la, snapshot.timezone))
    rest = max([p.min_rest_minutes for p in ps] or [0])
    if left.kind == "night":
        rest = max(rest, max([p.after_night_rest_minutes for p in ps] or [0]))
        if right.kind != "night":
            rest = max(rest, max([p.after_night_block_rest_minutes for p in ps] or [0]))
    return "rest" if ra - lb < rest else None


def night_block_conflict(snapshot, employee, left, right):
    """Extra block rest applies to consecutive selected duties, not arbitrary pairs."""
    if left.kind != "night" or right.kind != "night":
        return False
    la, lb = bounds(left)
    ra, rb = bounds(right)
    ps = profiles_for(
        snapshot, employee, local_day(la, snapshot.timezone)
    ) + profiles_for(snapshot, employee, local_day(ra, snapshot.timezone))
    gap = (local_day(ra, snapshot.timezone) - local_day(la, snapshot.timezone)).days
    return any(
        gap > p.night_block_gap_days and ra - lb < p.after_night_block_rest_minutes
        for p in ps
    )
