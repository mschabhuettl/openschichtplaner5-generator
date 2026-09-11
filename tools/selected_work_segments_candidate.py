"""Bridge the explicit-plan source candidate to measurement, not rule approval.

The injected selector is the patched API _employee_plan. Its source/date filtering
is a separate coverage limitation. Identities below are request-local, not DB keys.
"""
from dataclasses import dataclass
from datetime import date

from sp5lib import calculations as calc

from tools.work_segments_candidate import Duty, measure_duty


@dataclass(frozen=True)
class SelectedDuty:
    source_id: str
    day: date
    status: str
    duty: Duty | None = None
    issues: tuple[str, ...] = ()


def measure_selected(db, selector, employee_id, start, end, plan, zone):
    """Account for every selected row, including replacement and measurement gaps.

    Absence coexistence stays unresolved; do not subtract or discard work. No
    total is supplied: missing rows must not look like zero-hour validated work.
    """
    if plan not in ('ist', 'soll'):
        raise ValueError('Explicit ist or soll required')
    # The API selector silently omits unknown/invalid dates. Their period
    # membership cannot be established, so reject selected-source ambiguity
    # before it disappears. This does not certify cycle or snapshot coverage.
    for source in ('MASHI', 'SPSHI'):
        if source == 'SPSHI' and plan == 'soll':
            continue
        for row in db._read(source):
            if row.get('EMPLOYEEID') != employee_id:
                continue
            if source == 'MASHI' and ((int(row.get('TYPE') or 0) == 1) != (plan == 'soll')):
                continue
            try:
                source_day = calc.to_date(row.get('DATE'))
            except (TypeError, ValueError):
                source_day = None
            if type(source_day) is not date:
                # No original field content or employee identity in the error.
                raise ValueError(f'Unresolved {source} source date')
    # Missing cycle positions are free days, not missing cycle definitions.
    def required_date(value, source):
        try:
            parsed = calc.to_date(value)
        except (TypeError, ValueError):
            parsed = None
        if type(parsed) is not date:
            raise ValueError(f'Unresolved {source} source date')
        return parsed

    cycles = {int(row.get('ID') or 0): row for row in db._read('CYCLE')}
    relevant_assignments = set()
    for row in db._read('CYASS'):
        if row.get('EMPLOYEEID') != employee_id:
            continue
        first = required_date(row.get('START'), 'CYASS')
        last = (required_date(row['END'], 'CYASS')
                if row.get('END') not in (None, '') else None)
        if last is not None and last < first:
            raise ValueError('Unresolved CYASS reversed interval')
        if first > end or (last is not None and last < start):
            continue
        definition = cycles.get(int(row.get('CYCLEID') or 0))
        if definition is None:
            raise ValueError('Unresolved CYCLE definition')
        try:
            size = int(definition.get('SIZE') or 0)
        except (ValueError, TypeError):
            size = 0
        if size <= 0:
            raise ValueError('Unresolved CYCLE length')
        relevant_assignments.add(int(row.get('ID') or 0))
    for row in db._read('CYEXC'):
        if (row.get('EMPLOYEEID') == employee_id
                and int(row.get('CYCLEASSID') or 0) in relevant_assignments):
            required_date(row.get('DATE'), 'CYEXC')
    manual, cycle, special = selector(db, employee_id, start, end, plan)
    holidays = calc.holiday_calendar(db._read('HOLID'))
    shifts = {int(row['ID']): row for row in db._read('SHIFT')}
    replaced = {day for day, row in special if int(row.get('SHIFTID') or 0)}
    absence_days = set()
    for row in db._read('ABSEN'):
        if row.get('EMPLOYEEID') != employee_id:
            continue
        # Invalid relevant source dates deliberately fail; never certify omission.
        day = calc.to_date(row.get('DATE'))
        if day is None:
            raise ValueError('Unresolved absence date')
        absence_days.add(day)
    result = []
    for source, rows in [('MASHI', manual), ('CYCLE', cycle), ('SPSHI', special)]:
        for ordinal, (day, row) in enumerate(rows):
            identity = f'{source}:{ordinal}'
            if source != 'SPSHI' and day in replaced:
                result.append(SelectedDuty(identity, day, 'replaced'))
                continue
            issues = ('absence_coexists_unresolved',) if day in absence_days else ()
            if source == 'SPSHI':
                windows = row.get('STARTEND')
            else:
                shift = shifts.get(int(row.get('SHIFTID') or 0))
                if shift is None:
                    result.append(SelectedDuty(identity, day, 'unmeasurable',
                                               issues=issues + ('shift_missing',)))
                    continue
                windows = shift.get(f'STARTEND{calc.day_index(day, holidays)}')
            try:
                duty = measure_duty(identity, day, str(windows or ''), zone)
            except ValueError:
                result.append(SelectedDuty(identity, day, 'unmeasurable',
                                           issues=issues + ('segments_unresolved',)))
            else:
                if absence_days.intersection(duty.calendar_minutes(zone)):
                    issues = ('absence_coexists_unresolved',)
                result.append(SelectedDuty(identity, day, 'measured', duty, issues))
    return tuple(result)
