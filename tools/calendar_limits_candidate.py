"""Observed elapsed calendar sums against explicit generator profiles.

Diagnostic only: caller-declared covered days do not establish source coverage.
No CALCBASE, paid time, target or inferred weekly maximum enters this layer.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from sp5generator.timeutils import dates


@dataclass(frozen=True)
class LimitCheck:
    profile_id: str
    code: str
    day: date
    observed_minutes: int
    maximum_minutes: int
    missing_days: tuple[date, ...]

    @property
    def observed_exceeds(self):
        return self.observed_minutes > self.maximum_minutes


@dataclass(frozen=True)
class CalendarReport:
    checks: tuple[LimitCheck, ...]
    unresolved: tuple[str, ...]
    complete: bool = False


@dataclass(frozen=True)
class CalendarSourceWindow:
    first_day: date
    last_day: date
    source_start: date
    source_end: date


def calendar_source_window(active_days, *, weekly):
    """Required date-selection envelope for native calendar work sums only.

    Include measured planning spill days in active_days. For weekly checks fetch
    whole ISO weeks, then one preceding local date for incoming native segments.
    _parse_native_windows restricts starts to 00:00..23:59 and ends to the same
    or next local date; this bound is NOT a universal maximum duty duration.
    No elapsed-24h subtraction (DST), rest horizon or source coverage assertion.
    Fetch the envelope in ONE selector call: source identities are request-local.
    """
    days = tuple(active_days)
    if not days or any(type(day) is not date for day in days):
        raise ValueError('Explicit nonempty calendar dates required')
    first, last = min(days), max(days)
    try:
        if weekly:
            first -= timedelta(days=first.weekday())
            last += timedelta(days=6 - last.weekday())
        return CalendarSourceWindow(first, last, first - timedelta(days=1), last)
    except OverflowError:
        raise ValueError('Calendar context outside supported date range') from None


def diagnose_calendar(selected, profiles, profile_ids, start, end, zone, covered_days):
    """Single employee/selected plan; retain multiple applicable profile limits.

    Match generator validator semantics: each applicable weekly profile checks
    the whole ISO week, including context outside its own validity interval.
    In-period duties' spill days activate applicable future profiles as well.
    Source row dates identify planning duties; other duties remain fixed context.
    Overlap is NOT unioned away: sums are observed assignment minutes, not a
    certification of effective working time. Pair/absence diagnostics remain due.
    """
    if start > end:
        raise ValueError('Invalid period')
    selected, profiles = tuple(selected), tuple(profiles)
    if len({r.source_id for r in selected}) != len(selected):
        raise ValueError('Duty identities must be unique within the request')
    if len({p.id for p in profiles}) != len(profiles):
        raise ValueError('Profile identities must be unique')
    covered_days = set(covered_days)
    daily = defaultdict(int)
    planning_days = set()
    unresolved = ['source_coverage_unverified', 'other_rules_not_evaluated']
    for row in selected:
        if row.status == 'replaced':
            continue
        if row.status != 'measured' or row.duty is None or row.issues:
            unresolved.append(f'source:{row.source_id}')
        if row.status == 'measured' and row.duty is not None:
            amounts = row.duty.calendar_minutes(zone)
            for day, value in amounts.items():
                daily[day] += value
            if start <= row.day <= end:
                planning_days.update(amounts)
    assigned = set(profile_ids)
    by_id = {p.id: p for p in profiles}
    unresolved.extend(f'profile_missing:{pid}' for pid in sorted(assigned - by_id.keys()))
    required_days = set(dates(start, end)) | planning_days
    applicable_days = set()
    checks = []
    for pid in sorted(assigned & by_id.keys()):
        profile = by_id[pid]
        active = {d for d in required_days if profile.valid_from <= d <= profile.valid_until}
        if not active:
            continue
        if not profile.confirmed:
            unresolved.append(f'profile_unconfirmed:{pid}')
            continue
        applicable_days.update(active)
        if profile.max_daily_minutes is not None:
            for day in sorted(active):
                checks.append(LimitCheck(pid, 'daily_limit', day, daily[day],
                                         profile.max_daily_minutes,
                                         () if day in covered_days else (day,)))
        if profile.max_weekly_minutes is not None:
            for monday in sorted({d - timedelta(days=d.weekday()) for d in active}):
                week = tuple(monday + timedelta(days=i) for i in range(7))
                checks.append(LimitCheck(pid, 'weekly_limit', monday,
                                         sum(daily[d] for d in week),
                                         profile.max_weekly_minutes,
                                         tuple(d for d in week if d not in covered_days)))
    if required_days - applicable_days:
        unresolved.append('profile_days_uncovered')
    if any(check.missing_days for check in checks):
        unresolved.append('calendar_context_incomplete')
    return CalendarReport(tuple(checks), tuple(unresolved))
