"""Synthetic acceptance checks for the isolated measurement layer only."""
from datetime import date

import pytest

from tools.work_segments_candidate import measure_duty

ZONE = 'Europe/Vienna'


def test_split_duty_preserves_gap_and_identity():
    duty = measure_duty('synthetic:1', date(2026, 1, 5), '08:00-12:00 16:00-20:00', ZONE)
    assert duty.source_id == 'synthetic:1'
    assert len(duty.segments) == 2
    assert duty.calendar_minutes(ZONE) == {date(2026, 1, 5): 480}


@pytest.mark.parametrize(('day', 'minutes'), [(date(2026, 3, 29), 1380),
                                             (date(2026, 10, 25), 1500)])
def test_full_local_day_uses_elapsed_minutes(day, minutes):
    duty = measure_duty('synthetic:dst', day, '00:00-24:00', ZONE)
    assert duty.calendar_minutes(ZONE) == {day: minutes}


def test_sunday_overnight_split_by_iso_week():
    duty = measure_duty('synthetic:week', date(2026, 1, 11), '20:00-08:00', ZONE)
    assert duty.iso_week_minutes(ZONE) == {(2026, 2): 240, (2026, 3): 480}


def test_iso_year_not_calendar_year():
    duty = measure_duty('synthetic:year', date(2027, 1, 3), '20:00-08:00', ZONE)
    assert duty.iso_week_minutes(ZONE) == {(2026, 53): 240, (2027, 1): 480}


@pytest.mark.parametrize('windows', ['', '00:00-00:00', '08:00-12:00 broken',
                                      '08:70-16:00', '25:00-26:00',
                                      '08:00-12:00 11:00-16:00'])
def test_invalid_or_incomplete_segments_not_silently_counted(windows):
    with pytest.raises(ValueError):
        measure_duty('synthetic:bad', date(2026, 1, 5), windows, ZONE)


@pytest.mark.parametrize('day', [date(2026, 3, 29), date(2026, 10, 25)])
def test_dst_endpoint_requires_resolution(day):
    with pytest.raises(ValueError):
        measure_duty('synthetic:fold', day, '02:30-04:00', ZONE)


def test_nonmidnight_equal_endpoints_remain_full_day():
    duty = measure_duty('synthetic:24h', date(2026, 1, 5), '08:00-08:00', ZONE)
    assert duty.calendar_minutes(ZONE) == {date(2026, 1, 5): 960, date(2026, 1, 6): 480}
