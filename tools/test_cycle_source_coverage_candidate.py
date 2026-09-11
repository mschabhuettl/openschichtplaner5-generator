"""Synthetic cycle-source losses; no original project data."""
from datetime import date
from types import SimpleNamespace

import pytest
from sp5lib import calculations as calc
from tools.selected_work_segments_candidate import measure_selected

DAY = date(2026, 1, 5)


def data():
    return {'CYASS': [{'ID': 3, 'EMPLOYEEID': 10, 'CYCLEID': 1,
                       'START': str(DAY), 'END': None}],
            'CYCLE': [{'ID': 1, 'SIZE': 1, 'UNIT': 0}], 'CYENT': []}


def expand(t):
    return calc.expand_cycle_assignments(t['CYASS'], cycles=t['CYCLE'],
        cycle_entries=t['CYENT'], cycle_exceptions=t.get('CYEXC', []), von=DAY, bis=DAY)


def measure(t):
    return measure_selected(SimpleNamespace(_read=lambda n: t.get(n, [])),
        lambda *_: ([], [], []), 10, DAY, DAY, 'ist', 'Europe/Vienna')


@pytest.mark.parametrize('problem', ['start', 'definition', 'size'])
def test_library_silently_omits_unresolved_cycle(problem):
    t = data()
    if problem == 'start':
        t['CYASS'][0]['START'] = None
    elif problem == 'definition':
        t['CYCLE'] = []
    else:
        t['CYCLE'][0]['SIZE'] = 0
    assert expand(t) == []
    with pytest.raises(ValueError, match='Unresolved CY'):
        measure(t)


@pytest.mark.parametrize('value', [None, '', 'invalid'])
def test_relevant_exception_requires_date(value):
    t = data()
    t['CYEXC'] = [{'EMPLOYEEID': 10, 'CYCLEASSID': 3, 'DATE': value}]
    with pytest.raises(ValueError, match='Unresolved CYEXC'):
        measure(t)


@pytest.mark.parametrize('kind', ['open_end', 'free_day', 'foreign_person', 'outside'])
def test_valid_empty_cycles_not_invented_as_work(kind):
    t = data()
    if kind == 'foreign_person':
        t['CYASS'][0].update(EMPLOYEEID=11, START=None)
    elif kind == 'outside':
        t['CYASS'][0]['START'] = '2027-01-01'
        t['CYCLE'] = []
    elif kind == 'free_day':
        t['CYENT'] = [{'CYCLEEID': 1, 'INDEX': 0, 'SHIFTID': 0}]
    assert measure(t) == ()


def test_duplicate_cycle_position_is_order_dependent_in_library():
    t = data()
    t['CYENT'] = [{'CYCLEEID': 1, 'INDEX': 0, 'SHIFTID': shift}
                  for shift in (7, 0)]
    assert expand(t) == []
    t['CYENT'].reverse()
    assert expand(t)[0]['SHIFTID'] == 7
    with pytest.raises(ValueError, match='Unresolved CYENT duplicate position'):
        measure(t)


@pytest.mark.parametrize('position', [None, '', -1, 1, 0.5, 'invalid'])
def test_relevant_cycle_position_must_be_explicit_and_in_range(position):
    t = data()
    t['CYENT'] = [{'CYCLEEID': 1, 'INDEX': position, 'SHIFTID': 7}]
    with pytest.raises(ValueError, match='Unresolved CYENT position'):
        measure(t)


@pytest.mark.parametrize('unit,position', [(0, 0), (1, 6)])
def test_position_range_uses_day_or_week_model(unit, position):
    t = data()
    t['CYCLE'][0]['UNIT'] = unit
    t['CYENT'] = [{'CYCLEEID': 1, 'INDEX': position, 'SHIFTID': 0},
                  {'CYCLEEID': 2, 'INDEX': -9, 'SHIFTID': 7}]
    assert measure(t) == ()


def test_soll_does_not_validate_unselected_cycle_sources():
    t = data()
    t['CYASS'][0]['START'] = None
    result = measure_selected(SimpleNamespace(_read=lambda n: t.get(n, [])),
        lambda *_: ([], [], []), 10, DAY, DAY, 'soll', 'Europe/Vienna')
    assert result == ()


@pytest.mark.parametrize('reverse', [False, True])
def test_duplicate_selected_cycle_definition_is_not_resolved_by_order(reverse):
    t = data()
    t['CYCLE'].append({'ID': 1, 'SIZE': 0, 'UNIT': 0})
    t['CYENT'] = [{'CYCLEEID': 1, 'INDEX': 0, 'SHIFTID': 7}]
    if reverse:
        t['CYCLE'].reverse()
    # Actual Library behavior: identical assignment yields work or nothing.
    assert len(expand(t)) == (1 if reverse else 0)
    with pytest.raises(ValueError, match='Unresolved CYCLE ambiguous definition'):
        measure(t)


def test_identical_selected_cycle_duplicates_are_still_ambiguous():
    t = data()
    t['CYCLE'].append(dict(t['CYCLE'][0]))
    with pytest.raises(ValueError, match='Unresolved CYCLE ambiguous definition'):
        measure(t)


@pytest.mark.parametrize('scope', ['foreign_cycle', 'outside', 'foreign_person', 'soll'])
def test_unselected_cycle_duplicates_do_not_block(scope):
    t = data()
    t['CYCLE'].append(dict(t['CYCLE'][0]))
    if scope == 'foreign_cycle':
        t['CYASS'][0]['CYCLEID'] = 2
        t['CYCLE'].append({'ID': 2, 'SIZE': 1, 'UNIT': 0})
    elif scope == 'outside':
        t['CYASS'][0]['START'] = '2027-01-01'
    elif scope == 'foreign_person':
        t['CYASS'][0]['EMPLOYEEID'] = 11
    result = measure_selected(SimpleNamespace(_read=lambda n: t.get(n, [])),
        lambda *_: ([], [], []), 10, DAY, DAY,
        'soll' if scope == 'soll' else 'ist', 'Europe/Vienna')
    assert result == ()


@pytest.mark.parametrize('identical', [False, True])
def test_duplicate_assignment_identity_cannot_suppress_two_duties(identical):
    t = data()
    t['CYENT'] = [{'CYCLEEID': 1, 'INDEX': 0, 'SHIFTID': 7}]
    t['CYASS'].append(dict(t['CYASS'][0]))
    if not identical:
        t['CYCLE'].append({'ID': 2, 'SIZE': 1, 'UNIT': 0})
        t['CYENT'].append({'CYCLEEID': 2, 'INDEX': 0, 'SHIFTID': 8})
        t['CYASS'][1]['CYCLEID'] = 2
    assert len(expand(t)) == 2
    t['CYEXC'] = [{'EMPLOYEEID': 10, 'CYCLEASSID': 3, 'DATE': str(DAY), 'TYPE': 1}]
    assert expand(t) == []
    with pytest.raises(ValueError, match='Unresolved CYASS ambiguous identity'):
        measure(t)


@pytest.mark.parametrize('scope', ['foreign_person', 'outside', 'distinct'])
def test_independent_assignment_identities_remain_allowed(scope):
    t = data()
    t['CYASS'].append(dict(t['CYASS'][0]))
    if scope == 'foreign_person':
        t['CYASS'][1]['EMPLOYEEID'] = 11
    elif scope == 'outside':
        t['CYASS'][1]['START'] = '2027-01-01'
    else:
        t['CYASS'][1]['ID'] = 4
    assert measure(t) == ()


def test_duplicate_exception_dates_have_set_semantics():
    t = data()
    t['CYENT'] = [{'CYCLEEID': 1, 'INDEX': 0, 'SHIFTID': 7}]
    t['CYEXC'] = [{'ID': i, 'EMPLOYEEID': 10, 'CYCLEASSID': 3,
                   'DATE': str(DAY), 'TYPE': 1} for i in (1, 2)]
    assert expand(t) == []
    assert measure(t) == ()


@pytest.mark.parametrize('exception_type', [0, 1, None])
def test_library_exception_type_does_not_change_suppression(exception_type):
    # Characterization, not an endorsement of the API's 0=normal comment.
    t = data()
    t['CYENT'] = [{'CYCLEEID': 1, 'INDEX': 0, 'SHIFTID': 7}]
    assert len(expand(t)) == 1
    t['CYEXC'] = [{'EMPLOYEEID': 10, 'CYCLEASSID': 3,
                   'DATE': str(DAY), 'TYPE': exception_type}]
    assert expand(t) == []
