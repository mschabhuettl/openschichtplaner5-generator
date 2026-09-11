"""Synthetic integration with the real patched API selector; no HTTP/DBF data."""
import os
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.audit_upstream_work_time_plan import load_helpers
from tools.selected_work_segments_candidate import measure_selected

DAY = date(2026, 1, 5)


@pytest.fixture
def collect():
    selector = load_helpers(Path(os.environ['SP5_WORK_TIME_ROUTER']))._employee_plan
    def run(tables, plan='ist'):
        db = SimpleNamespace(_read=lambda name: tables.get(name, []))
        return measure_selected(db, selector, 10, DAY, DAY, plan, 'Europe/Vienna')
    return run


def tables():
    return {'MASHI': [{'EMPLOYEEID': 10, 'DATE': str(DAY), 'TYPE': kind,
                       'SHIFTID': 1} for kind in (0, 1)],
            'SHIFT': [{'ID': 1, 'NOEXTRA': 1, 'DURATION0': 3,
                       'STARTEND0': '08:00-12:00 16:00-20:00'}]}


@pytest.mark.parametrize('plan', ['ist', 'soll'])
def test_alternative_plans_not_added_and_noextra_not_removed(collect, plan):
    result = collect(tables(), plan)
    assert len(result) == 1
    assert result[0].duty.calendar_minutes('Europe/Vienna') == {DAY: 480}
    assert len(result[0].duty.segments) == 2


@pytest.mark.parametrize('shift_id', [0, 1])
def test_special_replacement_and_addition_preserve_source_accounting(collect, shift_id):
    data = tables()
    data['SPSHI'] = [{'EMPLOYEEID': 10, 'DATE': str(DAY), 'TYPE': 1,
                      'SHIFTID': shift_id, 'STARTEND': '20:00-22:00'}]
    result = collect(data)
    assert [r.status for r in result] == [
        'replaced' if shift_id else 'measured', 'measured']
    assert [r.source_id for r in result] == ['MASHI:0', 'SPSHI:0']
    assert len(collect(data, 'soll')) == 1


@pytest.mark.parametrize('failure', ['missing_shift', 'empty', 'invalid'])
def test_measurement_failure_stays_in_report(collect, failure):
    data = tables()
    if failure == 'missing_shift':
        data['SHIFT'] = []
    else:
        data['SHIFT'][0]['STARTEND0'] = '' if failure == 'empty' else '08:00-12:00 bad'
    result = collect(data)
    assert len(result) == 1
    assert result[0].status == 'unmeasurable'
    assert result[0].duty is None
    assert result[0].issues


@pytest.mark.parametrize('interval', range(4))
def test_absence_is_unresolved_not_subtracted(collect, interval):
    data = tables()
    data['ABSEN'] = [{'EMPLOYEEID': 10, 'DATE': str(DAY), 'INTERVAL': interval}]
    row, = collect(data)
    assert row.issues == ('absence_coexists_unresolved',)
    assert row.duty.calendar_minutes('Europe/Vienna') == {DAY: 480}


def test_holiday_slot_uses_library_day_index(collect):
    data = tables()
    data['HOLID'] = [{'DATE': str(DAY)}]
    data['SHIFT'][0]['STARTEND7'] = '10:00-12:00'
    row, = collect(data)
    assert row.duty.calendar_minutes('Europe/Vienna') == {DAY: 120}


def test_duplicate_duties_kept_separate_for_later_conflict_check(collect):
    data = tables()
    data['MASHI'].append(dict(data['MASHI'][0]))
    result = collect(data)
    assert len(result) == 2
    assert result[0].source_id != result[1].source_id
    assert all(row.status == 'measured' for row in result)


def test_mixed_plan_rejected(collect):
    with pytest.raises(ValueError, match='Explicit'):
        collect(tables(), None)


def test_overnight_absence_on_following_day_also_unresolved(collect):
    data = tables()
    data['SHIFT'][0]['STARTEND0'] = '20:00-08:00'
    data['ABSEN'] = [{'EMPLOYEEID': 10, 'DATE': '2026-01-06'}]
    row, = collect(data)
    assert row.issues == ('absence_coexists_unresolved',)


def test_cycle_used_in_ist_when_only_soll_manual_exists(collect):
    data = tables()
    data['MASHI'] = [data['MASHI'][1]]
    data.update({
        'CYCLE': [{'ID': 1, 'SIZE': 1, 'UNIT': 0}],
        'CYENT': [{'CYCLEEID': 1, 'INDEX': 0, 'SHIFTID': 1}],
        'CYASS': [{'EMPLOYEEID': 10, 'CYCLEID': 1, 'START': str(DAY),
                   'END': str(DAY), 'ENTRANCE': 0}],
    })
    row, = collect(data)
    assert row.source_id == 'CYCLE:0'
    assert row.duty.calendar_minutes('Europe/Vienna') == {DAY: 480}
    row, = collect(data, 'soll')
    assert row.source_id == 'MASHI:0'
