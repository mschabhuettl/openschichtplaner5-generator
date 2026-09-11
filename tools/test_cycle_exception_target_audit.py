"""Characterize OSP5's actual JS target selector against native cycle expansion.

No API writes, original records or copied replacement selector. This executes
the extracted upstream expression, not the full React save interaction.
"""
import json
import os
import re
import subprocess
from datetime import date
from pathlib import Path

import pytest
from sp5lib.calculations import expand_cycle_assignments

DAY = date(2026, 1, 5)


def selected_id(rows):
    frontend = Path(os.environ['SP5_OSP5_FRONTEND'])
    source = (frontend / 'src/pages/Schichtmodell.tsx').read_text()
    match = re.search(
        r'const getAssignmentId = \(empId: number\): number \| null =>\s*([^;]+);',
        source,
    )
    assert match, 'Upstream selector changed: re-audit instead of emulating it'
    program = (
        'const assignments = JSON.parse(process.argv[1]); const empId = 10;'
        f'process.stdout.write(JSON.stringify({match.group(1)}));'
    )
    return json.loads(subprocess.check_output(
        ['node', '-e', program, json.dumps(rows)], text=True,
    ))


def duties(assignments, target):
    return expand_cycle_assignments(
        assignments,
        cycles=[{'ID': 1, 'SIZE': 1, 'UNIT': 0}],
        cycle_entries=[{'CYCLEEID': 1, 'INDEX': 0, 'SHIFTID': 7}],
        cycle_exceptions=[{'EMPLOYEEID': 10, 'CYCLEASSID': target,
                           'DATE': str(DAY), 'TYPE': 1}],
        von=DAY, bis=DAY,
    )


@pytest.mark.parametrize('inactive', ['expired', 'future'])
@pytest.mark.parametrize('reverse', [False, True])
def test_first_person_assignment_can_leave_intended_duty(inactive, reverse):
    active = {'ID': 2, 'EMPLOYEEID': 10, 'CYCLEID': 1,
              'START': str(DAY), 'END': str(DAY)}
    other = dict(active, ID=1)
    if inactive == 'expired':
        other.update(START='2025-01-01', END='2026-01-04')
    else:
        other.update(START='2026-01-06', END=None)
    assignments = [other, active]
    if reverse:
        assignments.reverse()
    rows = [{'id': a['ID'], 'employee_id': a['EMPLOYEEID'],
             'start': a['START'], 'end': a['END']} for a in assignments]
    target = selected_id(rows)
    assert target == (2 if reverse else 1)
    # Native library bounds are inclusive: the active one-day assignment
    # disappears only when its identity, not the inactive identity, is chosen.
    assert len(duties(assignments, target)) == (0 if reverse else 1)


@pytest.mark.parametrize('reverse', [False, True])
def test_overlapping_distinct_cycles_are_not_a_person_wide_day_off(reverse):
    assignments = [{'ID': i, 'EMPLOYEEID': 10, 'CYCLEID': 1,
                    'START': str(DAY), 'END': None} for i in (1, 2)]
    if reverse:
        assignments.reverse()
    target = selected_id([{'id': a['ID'], 'employee_id': 10} for a in assignments])
    assert target == assignments[0]['ID']
    assert len(duties(assignments, target)) == 1
