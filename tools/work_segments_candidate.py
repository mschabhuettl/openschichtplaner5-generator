"""Isolated measurement candidate, NOT effective-source selection or a validator.

Input must be one already selected duty. Absence/replacement/source ambiguity,
paid time, required boundary context and cross-duty conflicts remain external.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sp5generator.sp5_adapter import _parse_native_windows
from sp5generator.timeutils import day_minutes, localize, minute


@dataclass(frozen=True)
class Segment:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class Duty:
    source_id: str
    segments: tuple[Segment, ...]

    def calendar_minutes(self, zone: str) -> dict[date, int]:
        return day_minutes(self, zone)

    def iso_week_minutes(self, zone: str) -> dict[tuple[int, int], int]:
        result = {}
        for day, duration in self.calendar_minutes(zone).items():
            iso = day.isocalendar()
            key = (iso.year, iso.week)
            result[key] = result.get(key, 0) + duration
        return result


def measure_duty(source_id: str, day: date, windows: str, zone: str) -> Duty:
    """Preserve split windows; reject malformed/ambiguous/overlapping input.

    No fold is guessed: source has no explicit fold contract yet. NOEXTRA and
    DURATION intentionally do not enter this measurement layer.
    """
    parts = []
    for start, end in _parse_native_windows(windows):
        if end <= start:
            end += 1440

        def endpoint(offset):
            days, clock = divmod(offset, 1440)
            hours, minutes = divmod(clock, 60)
            return localize(day + timedelta(days=days), f'{hours:02}:{minutes:02}', zone)

        part = Segment(endpoint(start), endpoint(end))
        if minute(part.end) <= minute(part.start):
            raise ValueError('Nonpositive elapsed segment')
        parts.append(part)
    if not parts:
        raise ValueError('Missing work segments')
    parts.sort(key=lambda part: minute(part.start))
    if any(minute(a.end) > minute(b.start) for a, b in zip(parts, parts[1:])):
        raise ValueError('Overlapping segments within duty')
    return Duty(source_id, tuple(parts))
