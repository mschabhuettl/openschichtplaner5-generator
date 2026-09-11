"""Synthetic characterization: surcharge intervals are not a work-time oracle.

Run against the original API via SP5_WORK_TIME_ROUTER and original sp5lib.
These tests document remaining gaps, not a corrected production validator.
"""
import os
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from sp5lib import calculations as calc

from tools.audit_upstream_work_time_plan import load_helpers


DAY = date(2026, 1, 5)
EMP = calc.EmployeeContext(workdays=(True,) * 8)


@pytest.mark.parametrize('kind', ['normal', 'replacement', 'additive'])
def test_noextra_excludes_surcharges_not_work(kind):
    shift = {'ID': 1, 'NOEXTRA': 1,
             **{f'STARTEND{i}': '08:00-16:00' for i in range(8)},
             **{f'DURATION{i}': 8 for i in range(8)}}
    normal = [{'DATE': str(DAY), 'SHIFTID': 1}] if kind == 'normal' else []
    special = [] if kind == 'normal' else [{
        'DATE': str(DAY), 'SHIFTID': 1 if kind == 'replacement' else 0,
        'NOEXTRA': 1 if kind == 'additive' else 0,
        'STARTEND': '08:00-16:00', 'DURATION': 8}]
    kwargs = dict(holidays={}, shifts_by_id={1: shift},
                  manual_shifts=normal, special_shifts=special)
    assert calc.get_work_hours(EMP, DAY, DAY, **kwargs) == 8
    assert calc.daily_work_intervals(EMP, DAY, DAY, **kwargs) == {}


def test_api_envelope_fills_split_duty_gap():
    helpers = load_helpers(Path(os.environ['SP5_WORK_TIME_ROUTER']))
    shift = {'ID': 1, **{f'STARTEND{i}': '08:00-12:00 16:00-20:00'
                         for i in range(8)},
             **{f'DURATION{i}': 8 for i in range(8)}}
    manual = [{'EMPLOYEEID': 10, 'DATE': str(DAY), 'SHIFTID': 1, 'TYPE': 0}]
    tables = {'MASHI': manual, 'SHIFT': [shift]}
    db = SimpleNamespace(_read=lambda table: tables.get(table, []))
    paid, blocks = helpers._collect_day_data(db, 10, DAY, DAY)
    assert paid == {DAY: 8}
    assert len(blocks) == 1
    assert (blocks[0]['end'] - blocks[0]['start']).total_seconds() == 12 * 3600
    # Reusing the envelope as elapsed work would incorrectly include a 4h gap.
    assert calc.daily_work_intervals(
        EMP, DAY, DAY, holidays={}, shifts_by_id={1: shift},
        manual_shifts=manual) == {DAY: [(480, 720), (960, 1200)]}


@pytest.mark.parametrize('interval', [0, 1, 2, 3])
def test_api_absence_does_not_resolve_work_segments(interval):
    helpers = load_helpers(Path(os.environ['SP5_WORK_TIME_ROUTER']))
    shift = {'ID': 1, **{f'STARTEND{i}': '08:00-16:00' for i in range(8)},
             **{f'DURATION{i}': 8 for i in range(8)}}
    tables = {'MASHI': [{'EMPLOYEEID': 10, 'DATE': str(DAY),
                          'SHIFTID': 1, 'TYPE': 0}], 'SHIFT': [shift]}
    db = SimpleNamespace(_read=lambda table: tables.get(table, []))
    before = helpers._collect_day_data(db, 10, DAY, DAY)
    tables['ABSEN'] = [{'EMPLOYEEID': 10, 'DATE': str(DAY), 'LEAVETYPID': 1,
                        'INTERVAL': interval, 'START': 600, 'END': 720}]
    assert helpers._collect_day_data(db, 10, DAY, DAY) == before
    # Source coexistence is evidenced; neither cancellation nor subtraction
    # is inferred from an absence record without an effective-work contract.
