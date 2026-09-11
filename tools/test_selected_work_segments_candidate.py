"""Synthetic integration with the real patched API selector; no HTTP/DBF data."""
import os
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from sp5generator.models import RuleProfile
from tools.calendar_limits_candidate import calendar_source_window, diagnose_calendar
from tools.audit_upstream_work_time_plan import load_helpers
from tools.duty_conflicts_candidate import diagnose_pairs
from tools.selected_work_segments_candidate import measure_selected

DAY = date(2026, 1, 5)


@pytest.mark.parametrize('value', [None, '', 'invalid'])
@pytest.mark.parametrize('plan', ['ist', 'soll'])
def test_unknown_holiday_date_cannot_silently_choose_weekday_hours(collect, value, plan):
    t = tables()
    t['SHIFT'][0].update(STARTEND0='08:00-16:00', STARTEND7='00:00-24:00')
    t['HOLID'] = [{'DATE': value}]
    with pytest.raises(ValueError, match='Unresolved HOLID source date'):
        collect(t, plan)


def test_duplicate_holiday_day_does_not_make_time_slot_ambiguous(collect):
    # day_index uses date membership, not INTERVAL or record identity.
    t = tables()
    t['SHIFT'][0]['STARTEND7'] = '08:00-16:00'
    t['HOLID'] = [{'DATE': str(DAY), 'INTERVAL': interval} for interval in (0, 1)]
    result = collect(t)
    assert result[0].duty.calendar_minutes('Europe/Vienna') == {DAY: 480}


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


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('plan', ['ist', 'soll'])
def test_duplicate_selected_shift_cannot_choose_eight_or_twentyfour_hours(collect, reverse, plan):
    t = tables()
    t['SHIFT'] = [{'ID': 1, 'STARTEND0': '08:00-16:00'},
                  {'ID': 1, 'STARTEND0': '00:00-24:00'}]
    if reverse:
        t['SHIFT'].reverse()
    result = collect(t, plan)
    assert len(result) == 1
    assert result[0].status == 'unmeasurable'
    assert result[0].duty is None
    assert result[0].issues == ('shift_ambiguous',)


def test_duplicate_unused_shift_does_not_block_selected_work(collect):
    t = tables()
    t['SHIFT'] += [{'ID': 2, 'STARTEND0': '08:00-16:00'},
                   {'ID': 2, 'STARTEND0': '00:00-24:00'}]
    result = collect(t)
    assert result[0].status == 'measured'
    assert result[0].duty.calendar_minutes('Europe/Vienna') == {DAY: 480}


@pytest.mark.parametrize('source', ['MASHI', 'SPSHI', 'CYCLE'])
def test_date_only_selection_loses_incoming_overnight_work(source):
    previous = DAY - timedelta(days=1)
    t = {'SHIFT': [{'ID': 1, 'STARTEND6': '22:00-06:00'}]}
    if source == 'MASHI':
        t[source] = [{'EMPLOYEEID': 10, 'DATE': str(previous), 'TYPE': 0,
                      'SHIFTID': 1}]
    elif source == 'SPSHI':
        t[source] = [{'EMPLOYEEID': 10, 'DATE': str(previous), 'SHIFTID': 0,
                      'STARTEND': '22:00-06:00'}]
    else:
        t.update(CYASS=[{'ID': 3, 'EMPLOYEEID': 10, 'CYCLEID': 1,
                         'START': str(previous), 'END': str(previous)}],
                 CYCLE=[{'ID': 1, 'SIZE': 1, 'UNIT': 0}],
                 CYENT=[{'CYCLEEID': 1, 'INDEX': 0, 'SHIFTID': 1}])
    selector = load_helpers(Path(os.environ['SP5_WORK_TIME_ROUTER']))._employee_plan
    db = SimpleNamespace(_read=lambda name: t.get(name, []))
    assert measure_selected(db, selector, 10, DAY, DAY, 'ist', 'Europe/Vienna') == ()
    window = calendar_source_window([DAY], weekly=True)
    contextual = measure_selected(db, selector, 10, window.source_start, window.source_end,
                                  'ist', 'Europe/Vienna')
    assert len(contextual) == 1
    assert contextual[0].duty.calendar_minutes('Europe/Vienna')[DAY] == 360
    # Previous Sunday belongs to a different ISO week; Monday's six hours do not.
    iso = DAY.isocalendar()
    assert contextual[0].duty.iso_week_minutes('Europe/Vienna')[iso.year, iso.week] == 360


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
    report = diagnose_pairs(result, 660)
    assert [(f.left, f.right, f.code) for f in report.findings] == [
        ('MASHI:0', 'MASHI:1', 'overlap')]
    assert report.complete is False


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


@pytest.mark.parametrize(('plan', 'special_id', 'expected'), [
    ('ist', 0, 600), ('ist', 1, 120), ('soll', 0, 480), ('soll', 1, 480)])
def test_selected_source_to_explicit_calendar_limit(collect, plan, special_id, expected):
    data = tables()
    data['SPSHI'] = [{'EMPLOYEEID': 10, 'DATE': str(DAY), 'TYPE': 1,
                      'SHIFTID': special_id, 'STARTEND': '20:00-22:00'}]
    selected = collect(data, plan)
    profile = RuleProfile(id='explicit', valid_from=DAY, valid_until=DAY,
                          min_rest_minutes=660, confirmed=True, max_daily_minutes=500)
    result = diagnose_calendar(selected, [profile], ['explicit'], DAY, DAY,
                               'Europe/Vienna', {DAY})
    check, = result.checks
    assert check.observed_minutes == expected
    assert check.observed_exceeds == (expected > 500)
    assert result.complete is False


@pytest.mark.parametrize('source', ['MASHI', 'SPSHI'])
@pytest.mark.parametrize('invalid_date', [None, '', '2026-02-30'])
def test_api_selector_silently_omits_invalid_dated_source(source, invalid_date):
    data = {source: [{'EMPLOYEEID': 10, 'DATE': invalid_date, 'TYPE': 0}]}
    db = SimpleNamespace(_read=lambda name: data.get(name, []))
    selector = load_helpers(Path(os.environ['SP5_WORK_TIME_ROUTER']))._employee_plan
    assert selector(db, 10, DAY, DAY, 'ist') == ([], [], [])


@pytest.mark.parametrize('source', ['MASHI', 'SPSHI'])
@pytest.mark.parametrize('invalid_date', [None, '', '2026-02-30'])
def test_measurement_bridge_rejects_unknown_source_date(collect, source, invalid_date):
    data = tables()
    data.setdefault(source, []).append({'EMPLOYEEID': 10, 'DATE': invalid_date, 'TYPE': 0})
    with pytest.raises(ValueError, match=f'Unresolved {source} source date'):
        collect(data)


@pytest.mark.parametrize('source', ['MASHI', 'SPSHI'])
def test_unrelated_employee_bad_date_does_not_block(collect, source):
    data = tables()
    data.setdefault(source, []).append({'EMPLOYEEID': 99, 'DATE': 'invalid', 'TYPE': 0})
    assert len(collect(data)) == 1


def test_only_selected_plan_requires_dated_sources(collect):
    data = tables()
    data['MASHI'].append({'EMPLOYEEID': 10, 'DATE': None, 'TYPE': 0})
    data['SPSHI'] = [{'EMPLOYEEID': 10, 'DATE': None}]
    assert len(collect(data, 'soll')) == 1
    data = tables()
    data['MASHI'].append({'EMPLOYEEID': 10, 'DATE': None, 'TYPE': 1})
    assert len(collect(data, 'ist')) == 1


def test_valid_out_of_period_date_remains_outside_selection(collect):
    data = tables()
    data['MASHI'].append({'EMPLOYEEID': 10, 'DATE': '2026-01-06', 'TYPE': 0})
    assert len(collect(data)) == 1


@pytest.mark.parametrize('plan', ['ist', 'soll'])
def test_validation_and_selection_reuse_first_table_read(plan):
    from collections import Counter

    data = tables()
    reads = Counter()
    def read(name):
        reads[name] += 1
        # A second read sees the next database revision, after validation.
        if name == 'MASHI' and reads[name] > 1:
            return []
        return data.get(name, [])
    selector = load_helpers(Path(os.environ['SP5_WORK_TIME_ROUTER']))._employee_plan
    result = measure_selected(SimpleNamespace(_read=read), selector, 10, DAY, DAY,
                              plan, 'Europe/Vienna')
    assert len(result) == 1
    assert result[0].duty.calendar_minutes('Europe/Vienna') == {DAY: 480}
    assert all(count == 1 for count in reads.values())
    if plan == 'soll':
        assert not set(reads).intersection({'SPSHI', 'CYASS', 'CYCLE', 'CYENT', 'CYEXC'})


def test_source_cache_mutation_cannot_change_already_checked_rows():
    data = tables()
    def read(name):
        if name == 'SPSHI':
            # Library _read returns the shared cache list, not an isolated copy.
            data['MASHI'][0]['DATE'] = 'not-a-date'
        return data.get(name, [])
    selector = load_helpers(Path(os.environ['SP5_WORK_TIME_ROUTER']))._employee_plan
    result = measure_selected(SimpleNamespace(_read=read), selector, 10, DAY, DAY,
                              'ist', 'Europe/Vienna')
    assert len(result) == 1
    assert result[0].status == 'measured'


def test_selector_mutation_does_not_change_measurement_tables():
    data = tables()
    selector = load_helpers(Path(os.environ['SP5_WORK_TIME_ROUTER']))._employee_plan
    def mutating_selector(db, *args):
        db._read('SHIFT')[0]['STARTEND0'] = '08:00-08:00'
        return selector(db, *args)
    result = measure_selected(SimpleNamespace(_read=lambda name: data.get(name, [])),
                              mutating_selector, 10, DAY, DAY, 'ist', 'Europe/Vienna')
    assert result[0].duty.calendar_minutes('Europe/Vienna') == {DAY: 480}
    assert data['SHIFT'][0]['STARTEND0'] == '08:00-12:00 16:00-20:00'


def test_next_diagnostic_request_observes_new_source_revision():
    data = tables()
    db = SimpleNamespace(_read=lambda name: data.get(name, []))
    selector = load_helpers(Path(os.environ['SP5_WORK_TIME_ROUTER']))._employee_plan
    first = measure_selected(db, selector, 10, DAY, DAY, 'ist', 'Europe/Vienna')
    data['SHIFT'][0]['STARTEND0'] = '08:00-10:00'
    second = measure_selected(db, selector, 10, DAY, DAY, 'ist', 'Europe/Vienna')
    assert first[0].duty.calendar_minutes('Europe/Vienna') == {DAY: 480}
    assert second[0].duty.calendar_minutes('Europe/Vienna') == {DAY: 120}


def test_per_table_copy_does_not_claim_cross_table_atomicity():
    data = tables()
    def read(name):
        if name == 'SPSHI':
            # A different table can still change before its FIRST read.
            data['SHIFT'][0]['STARTEND0'] = '08:00-10:00'
        return data.get(name, [])
    selector = load_helpers(Path(os.environ['SP5_WORK_TIME_ROUTER']))._employee_plan
    selected = measure_selected(SimpleNamespace(_read=read), selector, 10, DAY, DAY,
                                'ist', 'Europe/Vienna')
    assert selected[0].duty.calendar_minutes('Europe/Vienna') == {DAY: 120}
    # Even measured records + covered dates are not a source coverage certificate.
    profile = RuleProfile(id='explicit', confirmed=True, valid_from=DAY,
                          valid_until=DAY, min_rest_minutes=660, max_daily_minutes=600)
    report = diagnose_calendar(selected, [profile], ['explicit'], DAY, DAY,
                               'Europe/Vienna', {DAY})
    assert not report.complete
    assert report.checks[0].observed_minutes == 120
