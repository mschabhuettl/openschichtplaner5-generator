"""Synthetic timezone counterexamples against the unchanged API helpers.

No API/DBF/customer records are loaded. These characterize upstream defects,
not a correction or evidence about the unavailable 600-second job.
"""
import os
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from sp5generator.timeutils import localize, minute
from tools.audit_upstream_work_time_plan import load_helpers
from tools.test_upstream_work_time_boundaries import rules


def source(records):
    tables = {'MASHI': [], 'SHIFT': []}
    for index, (day, times) in enumerate(records, 1):
        tables['MASHI'].append({'EMPLOYEEID': 10, 'DATE': str(day),
                                'TYPE': 0, 'SHIFTID': index})
        tables['SHIFT'].append({'ID': index,
                                **{f'STARTEND{i}': times for i in range(8)},
                                **{f'DURATION{i}': 1 for i in range(8)}})
    return SimpleNamespace(_read=lambda table: tables.get(table, []))


@pytest.mark.parametrize('day,next_start,elapsed,reported', [
    (date(2026, 3, 29), '10:00', 10, []),
    (date(2026, 10, 25), '09:00', 11, [10]),
])
def test_rest_uses_naive_clock_not_elapsed_time(day, next_start, elapsed, reported):
    helpers = load_helpers(Path(os.environ['SP5_WORK_TIME_ROUTER']))
    previous = day - timedelta(days=1)
    db = source([(previous, '20:00-23:00'), (day, f'{next_start}-12:00')])
    checked = helpers._check_employee(db, 10, previous, day, rules())
    assert [v['value'] for v in checked
            if v['type'] == 'min_rest_hours_between_shifts'] == reported
    real_rest = (minute(localize(day, next_start, 'Europe/Vienna'))
                 - minute(localize(previous, '23:00', 'Europe/Vienna'))) / 60
    assert real_rest == elapsed
    # Spring: false all-clear at 10h; autumn: false violation at exactly 11h.
    assert bool(reported) is not (real_rest < 11)


@pytest.mark.parametrize('day,error', [
    (date(2026, 3, 29), 'Nicht existierende'),
    (date(2026, 10, 25), 'Mehrdeutige'),
])
def test_unresolved_local_times_silently_become_naive_blocks(day, error):
    helpers = load_helpers(Path(os.environ['SP5_WORK_TIME_ROUTER']))
    db = source([(day, '02:30-04:00')])
    hours, blocks = helpers._collect_day_data(db, 10, day, day)
    assert hours == {day: 1}
    assert len(blocks) == 1 and blocks[0]['start'].tzinfo is None
    assert helpers._check_employee(db, 10, day, day, rules()) == []
    with pytest.raises(ValueError, match=error):
        localize(day, '02:30', 'Europe/Vienna')
