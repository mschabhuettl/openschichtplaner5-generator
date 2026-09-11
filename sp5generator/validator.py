"""Independent arithmetic validation of proposed assignments, without solver state."""

from collections import defaultdict
from datetime import timedelta, datetime, timezone
from itertools import combinations
from zoneinfo import ZoneInfo
from .models import Diagnostic, Validation
from .domain import (
    MAX_ASSIGNMENTS,
    input_diagnostics,
    eligibility,
    pair_conflict,
    supervised,
    night_block_conflict,
    maximum_matching,
)
from .timeutils import (
    bounds,
    minute,
    segments,
    local_day,
    midnight,
    dates,
    day_minutes,
    longest_free,
)


def weekly_windows(snapshot, profile, spans, employee=None, planning_duty_days=()):
    """All critical minute-aligned windows, not a weekday sampling.

    Elapsed windows use endpoints at each free-gap's coverage boundary. Local
    windows enumerate all minute anchors: this deliberately favors correctness
    for the less common DST-sensitive rule over a sampling approximation.
    """
    start = midnight(snapshot.period_start, snapshot.timezone)
    end = midnight(snapshot.period_end + timedelta(days=1), snapshot.timezone)
    context_a = midnight(snapshot.context_start, snapshot.timezone)
    context_b = midnight(snapshot.context_end + timedelta(days=1), snapshot.timezone)
    required = profile.weekly_rest_minutes + (
        profile.min_rest_minutes if profile.weekly_rest_add_daily else 0
    )
    applicable = [
        p for p in snapshot.profiles if employee and p.id in employee.profile_ids
    ]

    def required_at(a, b):
        daily = max(
            [profile.min_rest_minutes]
            + [
                p.min_rest_minutes
                for p in applicable
                if p.valid_from <= local_day(b - 1, snapshot.timezone)
                and p.valid_until >= local_day(a, snapshot.timezone)
            ]
        )
        return profile.weekly_rest_minutes + (
            daily if profile.weekly_rest_add_daily else 0
        )

    if profile.weekly_rest_frame == "calendar_week":
        first = snapshot.period_start - timedelta(days=snapshot.period_start.weekday())
        weeks = {day for day in dates(first, snapshot.period_end) if day.weekday() == 0}
        weeks.update(
            day - timedelta(days=day.weekday()) for day in planning_duty_days
            if profile.valid_from <= day <= profile.valid_until
        )
        for day in sorted(weeks):
            a, b = (
                midnight(day, snapshot.timezone),
                midnight(day + timedelta(days=7), snapshot.timezone),
            )
            yield a, b, required_at(a, b)
    elif profile.weekly_rest_frame == "rolling_elapsed":
        length = profile.weekly_rest_window_days * 1440
        lo, hi = start - length + 1, end - 1
        anchors = {lo, hi}
        # F(t)=max clipped free gaps is piecewise linear. A threshold can
        # change only at u+R-W or v-R, where [u,v] is a free gap.
        points = {context_a, context_b}
        for a, b in spans:
            points.update((a, b))
        possible_required = {required} | {
            profile.weekly_rest_minutes + p.min_rest_minutes
            for p in applicable
            if profile.weekly_rest_add_daily
        }
        for p in applicable:
            # Profiles may be valid indefinitely. Only boundaries inside the
            # inspected context can change a relevant window's requirement.
            if snapshot.context_start <= p.valid_from <= snapshot.context_end:
                boundary = midnight(p.valid_from, snapshot.timezone)
                points.update((boundary, boundary + length))
            if snapshot.context_start <= p.valid_until < snapshot.context_end:
                boundary = midnight(p.valid_until + timedelta(days=1), snapshot.timezone)
                points.update((boundary, boundary + length))
        for point in points:
            for r in possible_required:
                for anchor in (point + r - length, point - r, point, point - length):
                    anchors.update((anchor - 1, anchor, anchor + 1))
        for anchor in sorted(x for x in anchors if lo <= x <= hi):
            yield anchor, anchor + length, required_at(anchor, anchor + length)
    else:
        tz = ZoneInfo(snapshot.timezone)
        lo = (
            midnight(
                snapshot.period_start - timedelta(days=profile.weekly_rest_window_days),
                snapshot.timezone,
            )
            + 1
        )
        for anchor in range(lo, end):
            local = datetime.fromtimestamp(anchor * 60, timezone.utc).astimezone(tz)
            finish = local + timedelta(days=profile.weekly_rest_window_days)
            finish_minute = int(finish.timestamp()) // 60
            if finish_minute > start:
                yield anchor, finish_minute, required_at(anchor, finish_minute)


class PreparedValidator:
    """Repeated arithmetic checks against an isolated, unchanged snapshot.

    A planning heuristic checks many proposals for the same input. Its private
    copy lets us check input integrity once without accepting stale public
    snapshots or trusting any of the solver's constraints.
    """

    def __init__(self, snapshot):
        self._snapshot = snapshot.model_copy(deep=True)
        self._input_errors = input_diagnostics(self._snapshot)

    def validate(self, assignments):
        return _validate(self._snapshot, assignments, self._input_errors)


def validate(snapshot, assignments):
    return _validate(snapshot, assignments)


def _validate(snapshot, assignments, input_errors=None):
    if len(assignments) > MAX_ASSIGNMENTS:
        return Validation(valid=False, complete=False, diagnostics=[Diagnostic(
            code="size_limit", message="Höchstens 5000 Einteilungen pro Prüfung sind unterstützt."
        )])
    errors = (
        input_diagnostics(snapshot) if input_errors is None else list(input_errors)
    )
    if errors:
        return Validation(valid=False, complete=False, diagnostics=errors)
    employees = {e.id: e for e in snapshot.employees}
    demands = {d.id: d for d in snapshot.demands}
    shifts = {s.id: s for s in snapshot.shifts}
    positions = {p.id: p for p in snapshot.positions}
    by_employee, by_demand = defaultdict(list), defaultdict(list)
    seen = set()
    fixed = {(a.employee_id, a.demand_id) for a in snapshot.assignments if a.fixed}

    def add(code, message, employee=None, demand=None, day=None):
        errors.append(
            Diagnostic(
                code=code,
                message=message,
                employee_id=employee,
                demand_id=demand,
                date=str(day) if day else None,
            )
        )

    for a in assignments:
        key = a.employee_id, a.demand_id
        if key in seen:
            add("duplicate", "Doppelte Einteilung.", a.employee_id, a.demand_id)
            continue
        seen.add(key)
        if a.employee_id not in employees or a.demand_id not in demands:
            add("reference", "Unbekannte Einteilung.", a.employee_id, a.demand_id)
            continue
        d = demands[a.demand_id]
        e = employees[a.employee_id]
        day = local_day(bounds(shifts[d.shift_id])[0], snapshot.timezone)
        if not snapshot.period_start <= day <= snapshot.period_end and key not in fixed:
            add(
                "context_assignment",
                "Außerhalb des Planungszeitraums sind nur vorhandene Fixierungen zulässig.",
                e.id,
                d.id,
                day,
            )
        try:
            intervals_match = not a.segments or [
                (minute(i.start), minute(i.end)) for i in a.segments
            ] == [
                (minute(i.start), minute(i.end)) for i in shifts[d.shift_id].segments
            ]
        except (ValueError, OverflowError):
            intervals_match = False
        if not intervals_match:
            add(
                "interval_mismatch",
                "Ergebnisintervalle stimmen nicht mit dem Snapshot überein.",
                e.id,
                d.id,
            )
        for reason in eligibility(snapshot, e, d):
            add(
                reason,
                "Einsatz nicht zulässig: " + reason,
                e.id,
                d.id,
                local_day(bounds(shifts[d.shift_id])[0], snapshot.timezone),
            )
        by_employee[e.id].append((a, shifts[d.shift_id]))
        by_demand[d.id].append(a)
    for a in snapshot.assignments:
        if a.fixed and (a.employee_id, a.demand_id) not in seen:
            add("fixed", "Fixierte Einteilung fehlt.", a.employee_id, a.demand_id)
    for d in snapshot.demands:
        count = len(by_demand[d.id])
        if count < d.minimum:
            add("vacancy", f"{d.minimum - count} unbesetzte Stelle(n).", demand=d.id)
        if d.maximum is not None and count > d.maximum:
            add("maximum", "Höchstbesetzung überschritten.", demand=d.id)
    # Immutable context comes from input, never the returned assignments. It
    # cannot satisfy demand, mentoring, or paid period targets.
    for work in snapshot.boundary_work:
        by_employee[work.employee_id].append((None, work))
    limit_context_end = snapshot.period_end
    for e in snapshot.employees:
        entries = by_employee[e.id]
        for (a, left), (b, right) in combinations(entries, 2):
            problem = pair_conflict(snapshot, e, left, right)
            if problem:
                add(
                    problem,
                    "Unvereinbare Dienste " + left.id + " / " + right.id,
                    e.id,
                    a.demand_id if a else None,
                )
        ordered = sorted(entries, key=lambda item: bounds(item[1])[0])
        for (a, left), (b, right) in zip(ordered, ordered[1:]):
            if night_block_conflict(snapshot, e, left, right):
                add(
                    "night_block",
                    "Zusätzliche Ruhe nach Nachtblock fehlt.",
                    e.id,
                    b.demand_id if b else None,
                )
        worked, nights, paid = set(), set(), 0
        planning_duty_days = set()
        daily = defaultdict(int)
        spans = []
        for a, s in entries:
            day = local_day(bounds(s)[0], snapshot.timezone)
            dm = day_minutes(s, snapshot.timezone)
            for d, n in dm.items():
                daily[d] += n
            worked.update(dm)
            if s.kind == "night":
                nights.add(day)
            if snapshot.period_start <= day <= snapshot.period_end:
                paid += s.paid_minutes
                planning_duty_days.update(dm)
            spans.extend(segments(s))
        for p in snapshot.profiles:
            if p.id not in e.profile_ids:
                continue
            active_days = set(
                dates(
                    max(p.valid_from, snapshot.period_start),
                    min(p.valid_until, snapshot.period_end),
                )
            )
            # A selected planning duty can run past the last planning date.
            # Its tail still consumes configured daily/weekly limits, together
            # with fixed context on the same day/week. Period totals stay scoped
            # to active_days; unrelated future context does not widen the check.
            limit_days = active_days | {
                day for day in planning_duty_days
                if p.valid_from <= day <= p.valid_until
            }
            for day in sorted(limit_days):
                if p.max_daily_minutes is not None and daily[day] > p.max_daily_minutes:
                    add(
                        "daily_limit",
                        "Tägliche Einsatzzeit überschritten.",
                        e.id,
                        day=day,
                    )
            # Check every day before weekly diagnostics; an earlier failing
            # week must not hide later daily violations or other failing weeks.
            for week in sorted({day - timedelta(days=day.weekday()) for day in limit_days}):
                if p.max_weekly_minutes is not None:
                    limit_context_end = max(limit_context_end, week + timedelta(days=6))
                if (
                    p.max_weekly_minutes is not None
                    and sum(daily[week + timedelta(days=i)] for i in range(7))
                    > p.max_weekly_minutes
                ):
                    add(
                        "weekly_limit",
                        "Wöchentliche Einsatzzeit überschritten.",
                        e.id,
                        day=week,
                    )
            period_work = worked & active_days
            period_nights = nights & active_days
            weekends = {
                d - timedelta(days=d.weekday()) for d in period_work if d.weekday() >= 5
            }
            profile_minutes = sum(n for d, n in daily.items() if d in active_days)
            for value, limit, code in (
                (profile_minutes, p.max_period_minutes, "period_limit"),
                (len(period_work), p.max_work_days, "work_days"),
                (len(period_nights), p.max_nights, "nights"),
                (len(weekends), p.max_weekends, "weekends"),
            ):
                if limit is not None and value > limit:
                    add(code, "Persönliche Obergrenze überschritten: " + code, e.id)
            for occupied, limit, code in (
                (worked, p.max_consecutive_work_days, "consecutive_work"),
                (nights, p.max_consecutive_nights, "consecutive_nights"),
            ):
                if limit:
                    for day in dates(
                        max(p.valid_from, snapshot.period_start),
                        min(
                            p.valid_until,
                            snapshot.context_end,
                            snapshot.period_end + timedelta(days=limit),
                        ),
                    ):
                        if all(
                            day - timedelta(days=i) in occupied
                            for i in range(limit + 1)
                        ):
                            add(
                                code, "Dienstserie überschreitet Grenze.", e.id, day=day
                            )
                            break
            if p.weekly_rest_minutes:
                for a, b, required in weekly_windows(snapshot, p, spans, e, planning_duty_days):
                    if (
                        local_day(b - 1, snapshot.timezone) < p.valid_from
                        or local_day(a, snapshot.timezone) > p.valid_until
                    ):
                        continue
                    if a < midnight(
                        snapshot.context_start, snapshot.timezone
                    ) or b > midnight(
                        snapshot.context_end + timedelta(days=1), snapshot.timezone
                    ):
                        add("context", "Randkontext für Wochenruhe fehlt.", e.id)
                        break
                    if longest_free(spans, a, b) < required:
                        add(
                            "weekly_rest",
                            "Zusammenhängende Wochenruhe fehlt im Fenster "
                            + datetime.fromtimestamp(a * 60, timezone.utc).isoformat()
                            + " bis "
                            + datetime.fromtimestamp(b * 60, timezone.utc).isoformat(),
                            e.id,
                        )
                        break
    # Bipartite matching assigns each supervised position to one real mentor.
    trainees = []
    mentor_edges = {}
    for a in assignments:
        if a.employee_id not in employees or a.demand_id not in demands:
            continue
        e, d = employees[a.employee_id], demands[a.demand_id]
        if not supervised(snapshot, e, d):
            continue
        s, p = shifts[d.shift_id], positions[d.position_id]
        options = []
        for other in assignments:
            if (
                other.employee_id == e.id
                or other.employee_id not in employees
                or other.demand_id not in demands
            ):
                continue
            mentor = employees[other.employee_id]
            md = demands[other.demand_id]
            ms, mp = shifts[md.shift_id], positions[md.position_id]
            if (
                mentor.mentor_capacity
                and mp.function_id == p.function_id
                and mp.workplace_id == p.workplace_id
                and not supervised(snapshot, mentor, md)
                and not eligibility(snapshot, mentor, d)
                and all(
                    any(x <= a0 and b0 <= y for x, y in segments(ms))
                    for a0, b0 in segments(s)
                )
            ):
                options.extend(
                    (other.employee_id, other.demand_id, i)
                    for i in range(mentor.mentor_capacity)
                )
        key = (a.employee_id, a.demand_id)
        trainees.append(key)
        mentor_edges[key] = options
    allocated = set(maximum_matching(mentor_edges).values())
    for key in trainees:
        if key not in allocated:
            add(
                "mentoring",
                "Keine gleichzeitig eingeteilte geeignete Betreuung mit freier Kapazität.",
                key[0],
                key[1],
            )
    horizon = max(
        [1]
        + [
            (
                max(
                    p.min_rest_minutes,
                    p.after_night_rest_minutes,
                    p.after_night_block_rest_minutes,
                )
                + 1439
            )
            // 1440
            for p in snapshot.profiles
        ]
        + [
            max(
                p.max_consecutive_work_days or 0,
                p.max_consecutive_nights or 0,
                p.weekly_rest_window_days if p.weekly_rest_minutes else 0,
                7 if p.max_weekly_minutes is not None else 0,
            )
            for p in snapshot.profiles
        ]
    )
    if snapshot.context_start > snapshot.period_start - timedelta(
        days=horizon
    ) or snapshot.context_end < max(
        snapshot.period_end + timedelta(days=horizon), limit_context_end
    ):
        add(
            "context",
            "Randkontext deckt aktive Ruhe-, Serien- oder Wochengrenzen nicht vollständig ab.",
        )
    if not snapshot.context_complete:
        add("context", "Vollständigkeit des Randkontexts ist nicht bestätigt.")
    # Demand shortages affect completeness, never excuse personal violations.
    return Validation(
        valid=not any(e.code not in ("vacancy", "context") for e in errors),
        complete=not errors,
        diagnostics=errors,
    )
