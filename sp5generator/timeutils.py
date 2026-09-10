"""Minute-resolution, half-open intervals; elapsed time is always measured in UTC."""

from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc


def minute(value: datetime) -> int:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Zeitpunkt benötigt expliziten UTC-Offset.")
    if value.second or value.microsecond:
        raise ValueError("Zeitpunkte müssen auf ganze Minuten fallen.")
    return int(value.timestamp()) // 60


def _local_datetime(day: date, clock: str) -> datetime:
    if clock == "24:00":
        day += timedelta(days=1)
        clock = "00:00"
    parsed = time.fromisoformat(clock)
    if parsed.tzinfo is not None or parsed.second or parsed.microsecond:
        raise ValueError("Lokale Uhrzeit muss ohne UTC-Offset und auf ganze Minuten angegeben werden.")
    return datetime.combine(day, parsed)


def localize(day: date, clock: str, zone: str, fold: int | None = None) -> datetime:
    if fold not in (None, 0, 1):
        raise ValueError("fold muss 0 oder 1 sein.")
    naive = _local_datetime(day, clock)
    tz = ZoneInfo(zone)
    candidates = []
    for f in (0, 1):
        candidate = naive.replace(tzinfo=tz, fold=f)
        back = candidate.astimezone(UTC).astimezone(tz)
        if back.replace(tzinfo=None) == naive and all(
            candidate.utcoffset() != c.utcoffset() for c in candidates
        ):
            candidates.append(candidate)
    if not candidates:
        raise ValueError("Nicht existierende lokale Uhrzeit: " + naive.isoformat())
    if len(candidates) > 1 and fold is None:
        raise ValueError(
            "Mehrdeutige lokale Uhrzeit benötigt fold: " + naive.isoformat()
        )
    return (
        candidates[0] if len(candidates) == 1 else naive.replace(tzinfo=tz, fold=fold)
    )


def availability_window(day, availability, zone):
    """Resolve the actual dates of an overnight window before DST validation."""
    start = _local_datetime(day, availability.start_time)
    end = _local_datetime(day, availability.end_time)
    if end <= start:
        end += timedelta(days=1)
    if end.date() > availability.valid_until:
        end = datetime.combine(availability.valid_until, time()) + timedelta(days=1)
    return (
        minute(localize(start.date(), start.strftime("%H:%M"), zone)),
        minute(localize(end.date(), end.strftime("%H:%M"), zone)),
    )


def midnight(day: date, zone: str) -> int:
    return minute(localize(day, "00:00", zone))


def local_day(value: int, zone: str) -> date:
    return datetime.fromtimestamp(value * 60, UTC).astimezone(ZoneInfo(zone)).date()


def dates(start: date, end: date):
    while start <= end:
        yield start
        start += timedelta(days=1)


def segments(shift):
    return sorted((minute(i.start), minute(i.end)) for i in shift.segments)


def bounds(shift):
    spans = segments(shift)
    return spans[0][0], spans[-1][1]


def overlap(a, b):
    return a[0] < b[1] and b[0] < a[1]


def day_minutes(shift, zone):
    out = {}
    for a, b in segments(shift):
        for day in dates(local_day(a, zone), local_day(b - 1, zone)):
            out[day] = out.get(day, 0) + max(
                0,
                min(b, midnight(day + timedelta(days=1), zone))
                - max(a, midnight(day, zone)),
            )
    return out


def longest_free(spans, a, b):
    cursor, best = a, 0
    for start, end in sorted(spans):
        if end <= a or start >= b:
            continue
        start, end = max(a, start), min(b, end)
        best = max(best, start - cursor)
        cursor = max(cursor, end)
    return max(best, b - cursor)
