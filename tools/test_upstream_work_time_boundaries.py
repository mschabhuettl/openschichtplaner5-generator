"""Characterize API/Generator differences using only synthetic duty records.

The assertions deliberately describe the UNFIXED upstream API, not a desired
validation contract. No API startup, network, DBF or customer data is used.
Run with the original library and generator tests directories on PYTHONPATH.
"""
import os
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from sp5generator.models import Assignment
from sp5generator.validator import validate
from test_core_rules import case, shift
from tools.audit_upstream_work_time_plan import load_helpers


@pytest.fixture
def helpers():
    return load_helpers(Path(os.environ['SP5_WORK_TIME_ROUTER']))


def source(duties):
    """(January day, STARTEND, paid hours) -> original table-shaped records."""
    tables = {'MASHI': [], 'SHIFT': []}
    for index, (day, times, paid) in enumerate(duties, 1):
        tables['MASHI'].append({'EMPLOYEEID': 10, 'DATE': f'2026-01-{day:02}',
                                'TYPE': 0, 'SHIFTID': index})
        tables['SHIFT'].append({'ID': index,
                                **{f'STARTEND{i}': times for i in range(8)},
                                **{f'DURATION{i}': paid for i in range(8)}})
    return SimpleNamespace(_read=lambda table: tables.get(table, []))


def rules(**overrides):
    # Deliberately permissive unrelated limits isolate each synthetic claim.
    return {'max_hours_per_day': 100, 'max_hours_per_week': 100,
            'min_rest_hours_between_shifts': 11, 'max_consecutive_days': 100,
            **overrides}


def codes(snapshot):
    checked = validate(snapshot, [Assignment(employee_id='e0', demand_id=d.id)
                                  for d in snapshot.demands])
    return {d.code for d in checked.diagnostics}


@pytest.mark.parametrize('cap', ['max_hours_per_day', 'max_hours_per_week'])
def test_paid_eight_hours_conceal_24_elapsed_hours(helpers, cap):
    db = source([(5, '08:00-08:00', 8)])
    assert helpers._check_employee(db, 10, date(2026, 1, 5), date(2026, 1, 6),
                                   rules(**{cap: 10})) == []
    snapshot = case(1, [shift('long', 5, 8, 24)])
    snapshot.shifts[0].paid_minutes = 480
    field, code = ('max_daily_minutes', 'daily_limit') if cap.endswith('day') else (
        'max_weekly_minutes', 'weekly_limit')
    setattr(snapshot.profiles[0], field, 600)
    assert code in codes(snapshot)


def test_start_day_booking_creates_false_daily_excess(helpers):
    db = source([(5, '12:00-12:00', 24)])
    result = helpers._check_employee(db, 10, date(2026, 1, 5), date(2026, 1, 6),
                                     rules(max_hours_per_day=12))
    assert [(v['type'], v['date'], v['value']) for v in result] == [
        ('max_hours_per_day', '2026-01-05', 24)]
    snapshot = case(1, [shift('noon', 5, 12, 24)])
    snapshot.profiles[0].max_daily_minutes = 720
    assert 'daily_limit' not in codes(snapshot)  # 12h on each calendar day.


def test_sunday_night_charged_to_wrong_iso_week(helpers):
    db = source([(11, '20:00-08:00', 12)])
    result = helpers._check_employee(db, 10, date(2026, 1, 11), date(2026, 1, 12),
                                     rules(max_hours_per_week=6))
    assert [(v['date'], v['value']) for v in result] == [('2026-01-05', 12)]
    snapshot = case(1, [shift('sunday', 11, 20, 12)])
    snapshot.period_end = date(2026, 1, 12)
    snapshot.profiles[0].max_weekly_minutes = 360
    checked = validate(snapshot, [Assignment(employee_id='e0', demand_id='sunday')])
    # Four hours belong to W02, eight to W03, not twelve to W02.
    assert [d.date for d in checked.diagnostics if d.code == 'weekly_limit'] == [
        '2026-01-12']


def test_partial_week_omits_same_week_work(helpers):
    db = source([(5, '08:00-16:00', 8), (7, '08:00-16:00', 8)])
    limits = rules(max_hours_per_week=12)
    full = helpers._check_employee(db, 10, date(2026, 1, 5), date(2026, 1, 7), limits)
    cropped = helpers._check_employee(db, 10, date(2026, 1, 7), date(2026, 1, 7), limits)
    assert [(v['type'], v['value']) for v in full] == [('max_hours_per_week', 16)]
    assert cropped == []


def test_range_start_omits_previous_duty_rest(helpers):
    db = source([(5, '20:00-23:00', 3), (6, '08:00-16:00', 8)])
    full = helpers._check_employee(db, 10, date(2026, 1, 5), date(2026, 1, 6), rules())
    cropped = helpers._check_employee(db, 10, date(2026, 1, 6), date(2026, 1, 6), rules())
    assert [(v['type'], v['value']) for v in full] == [
        ('min_rest_hours_between_shifts', 9)]
    assert cropped == []


def test_missing_normal_duty_times_are_not_reported_incomplete(helpers):
    db = source([(5, '', 24)])
    assert helpers._collect_day_data(db, 10, date(2026, 1, 5), date(2026, 1, 5)) == (
        {date(2026, 1, 5): 0}, [])
    assert helpers._check_employee(db, 10, date(2026, 1, 5), date(2026, 1, 5),
                                   rules(max_hours_per_day=10)) == []
