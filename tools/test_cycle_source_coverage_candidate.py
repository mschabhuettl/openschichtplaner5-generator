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
