"""Native date-selection bounds, not a full validation coverage certificate."""
from datetime import date, datetime

import pytest

from tools.calendar_limits_candidate import calendar_source_window
from tools.work_segments_candidate import measure_duty


def test_partial_iso_week_requires_previous_sunday_through_sunday():
    window = calendar_source_window([date(2026, 1, 7)], weekly=True)
    assert (window.first_day, window.last_day) == (date(2026, 1, 5), date(2026, 1, 11))
    assert (window.source_start, window.source_end) == (date(2026, 1, 4), date(2026, 1, 11))


def test_planning_spill_into_next_iso_year_expands_week_context():
    window = calendar_source_window([date(2027, 1, 3), date(2027, 1, 4)], weekly=True)
    assert (window.source_start, window.source_end) == (date(2026, 12, 27), date(2027, 1, 10))


@pytest.mark.parametrize('day,minutes', [(date(2026, 3, 29), 180),
                                       (date(2026, 10, 25), 300)])
def test_dst_uses_previous_local_date_not_fixed_elapsed_day(day, minutes):
    window = calendar_source_window([day], weekly=False)
    duty = measure_duty('synthetic', window.source_start, '23:00-04:00', 'Europe/Vienna')
    assert duty.calendar_minutes('Europe/Vienna')[day] == minutes
    assert window.source_end == day


@pytest.mark.parametrize('days', [[], [datetime(2026, 1, 5)], ['2026-01-05'],
                                  [date.min], [date.max]])
def test_unrepresentable_or_unspecified_context_rejected(days):
    with pytest.raises(ValueError):
        calendar_source_window(days, weekly=True)
