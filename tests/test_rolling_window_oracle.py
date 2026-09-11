"""Critical elapsed windows versus an exhaustive, independent interval oracle."""
from datetime import UTC, date, datetime, timedelta
from random import Random
from zoneinfo import ZoneInfo

import pytest

from test_core_rules import case
from sp5generator.models import RuleProfile
from sp5generator.validator import weekly_windows


def local_date(value, zone):
    return datetime.fromtimestamp(value * 60, UTC).astimezone(zone).date()


def free_gap(spans, start, end):
    # Partition at every occupied endpoint; merge adjacent empty cells.
    edges = sorted({start, end} | {
        max(start, min(end, value)) for span in spans for value in span
    })
    longest = current = 0
    for left, right in zip(edges, edges[1:]):
        if any(a < right and b > left for a, b in spans):
            current = 0
        else:
            current += right - left
            longest = max(longest, current)
    return longest


@pytest.mark.parametrize("day", [date(2026, 1, 5), date(2026, 3, 29), date(2026, 10, 25)])
@pytest.mark.parametrize("window_days", [1, 7])
@pytest.mark.parametrize("add_daily", [False, True])
@pytest.mark.parametrize("assigned", [False, True])
def test_elapsed_critical_windows_match_dated_dst_oracle(day, window_days, add_daily, assigned):
    s = case(1)
    s.timezone = "Europe/Vienna"
    zone = ZoneInfo(s.timezone)
    s.period_start = s.period_end = day
    s.context_start, s.context_end = day - timedelta(days=10), day + timedelta(days=10)
    p = s.profiles[0]
    p.valid_from = p.valid_until = day
    p.weekly_rest_frame = "rolling_elapsed"
    p.weekly_rest_window_days = window_days
    p.weekly_rest_minutes = 180 if window_days == 1 else 2160
    p.min_rest_minutes = 60
    p.weekly_rest_add_daily = add_daily
    q = RuleProfile(id="dated", valid_from=day - timedelta(days=1), valid_until=day - timedelta(days=1),
                    min_rest_minutes=660, confirmed=True)
    s.profiles.append(q)
    e = s.employees[0]
    if assigned:
        e.profile_ids.append(q.id)
    start = int(datetime.combine(day, datetime.min.time(), zone).timestamp()) // 60
    end = int(datetime.combine(day + timedelta(days=1), datetime.min.time(), zone).timestamp()) // 60
    assert end - start == {1: 1440, 3: 1380, 10: 1500}[day.month]
    length = window_days * 1440
    anchors = range(start - length + 1, end)

    def requirement(a, b):
        daily = max([p.min_rest_minutes] + [
            profile.min_rest_minutes for profile in s.profiles
            if profile.id in e.profile_ids
            and profile.valid_from <= local_date(b - 1, zone)
            and profile.valid_until >= local_date(a, zone)
        ])
        return p.weekly_rest_minutes + (daily if add_daily else 0)

    required_values = {requirement(a, a + length) for a in anchors}
    expected = {p.weekly_rest_minutes + p.min_rest_minutes, p.weekly_rest_minutes + 660}
    if assigned and add_daily:
        assert required_values == expected
    else:
        assert len(required_values) == 1

    rng = Random(420)
    patterns = [[], [(start - length, end + length)]]
    for _ in range(8):
        points = sorted(rng.sample(range(start - length, end + length), 12))
        patterns.append(list(zip(points[::2], points[1::2])))
    outcomes = set()
    for spans in patterns:
        windows = list(weekly_windows(s, p, spans, e))
        assert all(r == requirement(a, b) for a, b, r in windows)
        critical_bad = any(
            free_gap(spans, a, b) < r for a, b, r in windows
            if local_date(b - 1, zone) >= p.valid_from
            and local_date(a, zone) <= p.valid_until
        )
        brute_bad = any(
            free_gap(spans, a, a + length) < requirement(a, a + length)
            for a in anchors
            if local_date(a + length - 1, zone) >= p.valid_from
            and local_date(a, zone) <= p.valid_until
        )
        assert critical_bad == brute_bad, spans
        outcomes.add(brute_bad)
    assert outcomes == {False, True}
