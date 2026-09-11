"""Bridge the explicit-plan source candidate to measurement, not rule approval.

The injected selector is the patched API _employee_plan. Its source/date filtering
is a separate coverage limitation. Identities below are request-local, not DB keys.
"""
from dataclasses import dataclass
from copy import deepcopy
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


class _RequestTables:
    """Repeatable per-table reads, NOT an atomic cross-table DB snapshot.

    Library reads expose shared cached lists and may change between calls.
    Copy on capture and delivery prevents consumers mutating checked records.
    A missing table returned as [] by the library remains indistinguishable from
    an empty table; neither this wrapper nor its caller certifies source coverage.
    """

    def __init__(self, source):
        self.source = source
        self.tables = {}

    def _read(self, name):
        if name not in self.tables:
            self.tables[name] = deepcopy(self.source._read(name))
        return deepcopy(self.tables[name])


class StrictSourceTables:
    """Opt-in bridge to the patched Library reader, bypassing legacy cache.

    Use SP5Database._table for native path resolution and inject the candidate
    read_dbf. Errors propagate without a partial diagnostic. Request-local
    copying is still performed by measure_selected; this is not a snapshot.
    """

    def __init__(self, source, read_dbf):
        self.source = source
        self.read_dbf = read_dbf

    def _read(self, name):
        return self.read_dbf(self.source._table(name), strict=True)


def measure_selected(db, selector, employee_id, start, end, plan, zone):
    """Account for every selected row, including replacement and measurement gaps.

    Absence coexistence stays unresolved; do not subtract or discard work. No
    total is supplied: missing rows must not look like zero-hour validated work.
    """
    if plan not in ('ist', 'soll'):
        raise ValueError('Explicit ist or soll required')
    db = _RequestTables(db)
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
    if plan == 'ist':
        _validate_cycle_sources(db, employee_id, start, end)
    manual, cycle, special = selector(db, employee_id, start, end, plan)
    holiday_rows = db._read('HOLID')
    for row in holiday_rows:
        try:
            holiday_day = calc.to_date(row.get('DATE'))
        except (TypeError, ValueError):
            holiday_day = None
        if type(holiday_day) is not date:
            # Unknown period membership must not silently select weekday times.
            raise ValueError('Unresolved HOLID source date')
    holidays = calc.holiday_calendar(holiday_rows)
    shifts = {}
    for row in db._read('SHIFT'):
        shifts.setdefault(int(row['ID']), []).append(row)
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
                definitions = shifts.get(int(row.get('SHIFTID') or 0), [])
                if not definitions:
                    result.append(SelectedDuty(identity, day, 'unmeasurable',
                                               issues=issues + ('shift_missing',)))
                    continue
                if len(definitions) != 1:
                    result.append(SelectedDuty(identity, day, 'unmeasurable',
                                               issues=issues + ('shift_ambiguous',)))
                    continue
                shift = definitions[0]
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


def _validate_cycle_sources(db, employee_id, start, end):
    # Missing cycle positions are free days, not missing cycle definitions.
    def required_date(value, source):
        try:
            parsed = calc.to_date(value)
        except (TypeError, ValueError):
            parsed = None
        if type(parsed) is not date:
            raise ValueError(f'Unresolved {source} source date')
        return parsed

    cycles = {}
    for row in db._read('CYCLE'):
        cycles.setdefault(int(row.get('ID') or 0), []).append(row)
    relevant_assignments = set()
    relevant_lengths = {}
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
        assignment_id = int(row.get('ID') or 0)
        # Library exceptions use (employee, assignment ID), not cycle ID.
        # A collision would suppress multiple independently expanded duties.
        if assignment_id in relevant_assignments:
            raise ValueError('Unresolved CYASS ambiguous identity')
        definitions = cycles.get(int(row.get('CYCLEID') or 0), [])
        if not definitions:
            raise ValueError('Unresolved CYCLE definition')
        if len(definitions) != 1:
            raise ValueError('Unresolved CYCLE ambiguous definition')
        definition = definitions[0]
        try:
            size = int(definition.get('SIZE') or 0)
        except (ValueError, TypeError):
            size = 0
        if size <= 0:
            raise ValueError('Unresolved CYCLE length')
        cycle_id = int(row.get('CYCLEID') or 0)
        relevant_lengths[cycle_id] = size * (7 if int(definition.get('UNIT') or 0) == 1 else 1)
        relevant_assignments.add(assignment_id)
    positions = set()
    for row in db._read('CYENT'):
        cycle_id = int(row.get('CYCLEEID') or 0)
        if cycle_id not in relevant_lengths:
            continue
        # Expansion coerces absent INDEX to zero and overwrites duplicates.
        # Neither operation establishes which duty actually belongs here.
        raw = row.get('INDEX')
        try:
            position = int(raw)
        except (TypeError, ValueError, OverflowError):
            raise ValueError('Unresolved CYENT position') from None
        if (isinstance(raw, bool) or (not isinstance(raw, str) and raw != position)
                or not 0 <= position < relevant_lengths[cycle_id]):
            raise ValueError('Unresolved CYENT position')
        key = (cycle_id, position)
        if key in positions:
            raise ValueError('Unresolved CYENT duplicate position')
        positions.add(key)
    for row in db._read('CYEXC'):
        if (row.get('EMPLOYEEID') == employee_id
                and int(row.get('CYCLEASSID') or 0) in relevant_assignments):
            required_date(row.get('DATE'), 'CYEXC')
