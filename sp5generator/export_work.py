"""One work list for tabular detail, calendars and period accounting."""

from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, date, timedelta
import re
from zoneinfo import ZoneInfo

from .models import BoundaryWork, Shift
from .timeutils import day_of


@dataclass(frozen=True)
class ExportWork:
    employee_id: str
    reference_id: str
    work: Shift | BoundaryWork
    name: str
    position_name: str
    function_id: str
    workplace_id: str | int
    fixed: bool
    category: str
    day: date
    period_paid_minutes: int


MAX_CELL_TEXT = 32767
# XML-forbidden code points, plus CR: the XLSX writer can normalize raw CR to
# LF on readback. Optional labels must be portable without rewriting them.
UNUSABLE_PROVENANCE_TEXT = re.compile(r"[\x00-\x08\x0b-\x1f\ud800-\udfff\ufffe\uffff]")


def _provenance_text(value):
    """Return exact, nonblank portable text or the empty optional-field value.

    No trimming, normalization, truncation or coercion. Tabs/LF and Unicode
    remain literal; unsupported controls, surrogates and overlong text do not.
    Account for the existing formula-escape prefix without applying it twice.
    """
    from .export import safe_cell

    if (type(value) is not str or len(value) > MAX_CELL_TEXT
            or not value.strip() or UNUSABLE_PROVENANCE_TEXT.search(value)
            or len(safe_cell(value)) > MAX_CELL_TEXT):
        return ""
    return value


def _provenance_workplace(value):
    # The adapter emits native integer workplace IDs as well as string labels.
    # Reject bool, floats (including NaN/inf) and integers outside the portable
    # 15-digit numeric range; never round or stringify unsupported metadata.
    if type(value) is int and -999_999_999_999_999 <= value <= 999_999_999_999_999:
        return value
    return _provenance_text(value)


def _calendar_labels(snapshot, entry, zone):
    """Calendar text footprints, matching workbook's joins and decorations."""
    title = f"{'◆ ' if entry.fixed else ''}{entry.name}"
    if entry.position_name:
        title += " · " + entry.position_name
    if not entry.work.segments:
        if snapshot.period_start <= entry.day <= snapshot.period_end:
            yield entry.day, title + "\nohne Zeiten"
        return
    for interval in entry.work.segments:
        begin, end = interval.start.astimezone(zone), interval.end.astimezone(zone)
        last = (end.astimezone(UTC) - timedelta(microseconds=1)).astimezone(zone).date()
        time_label = f"{begin:%H:%M}–{end:%H:%M}"
        if begin.date() != end.date():
            days = (end.date() - begin.date()).days
            time_label += " (+1)" if days == 1 else f" (+{days})"
        day = max(begin.date(), snapshot.period_start)
        while day <= min(last, snapshot.period_end):
            yield day, title + "\n" + time_label
            day += timedelta(days=1)


def _fit_provenance_names(snapshot, entries):
    """Reserve core/fallback text before spending cell space on optional names.

    A scalar can fit a detail cell yet overflow a calendar cell when decorated,
    repeated for split intervals or joined to other work. Keep each accepted
    name exact in both formats; otherwise use its category everywhere. Never
    suppress a work record or trim mandatory source text to make room.
    """
    from .export import safe_cell

    zone = ZoneInfo(snapshot.timezone)
    used = defaultdict(int)
    occurrences = []
    for entry in entries:
        base = replace(entry, name=entry.category, position_name="") if isinstance(entry.work, BoundaryWork) else entry
        counts = Counter()
        for day, label in _calendar_labels(snapshot, base, zone):
            key = entry.employee_id, day
            used[key] += len(label) + 2 if used[key] else len(safe_cell(label))
            counts[key] += 1
        occurrences.append(counts)
    for entry, counts in zip(entries, occurrences):
        if isinstance(entry.work, BoundaryWork) and entry.position_name:
            # Fallback is "◆ category"; a name adds "name · " before category.
            extra = len(entry.name) + len(" · ")
            if any(used[key] + count * extra > MAX_CELL_TEXT for key, count in counts.items()):
                entry = replace(entry, name=entry.category, position_name="")
            else:
                for key, count in counts.items():
                    used[key] += count * extra
        yield entry


def export_work(snapshot, assignments):
    """Preserve personal work as work, never as an extra staffing assignment.

    Paid minutes belong only to work starting in the planning period; a context
    tail may be visible in the calendar without receiving a second credit.
    Untimed work retains its stated day and has no manufactured interval.

    Optional provenance is presentation only: name/function_id accept usable
    strings; workplace_id also accepts native integers in the portable numeric
    range. All other values use the category/empty-field fallback. The exact
    work ID, original records and accounting never depend on these labels.
    """
    demands = {d.id: d for d in snapshot.demands}
    shifts = {s.id: s for s in snapshot.shifts}
    positions = {p.id: p for p in snapshot.positions}
    entries = []
    for assignment in assignments:
        demand = demands[assignment.demand_id]
        work, position = shifts[demand.shift_id], positions[demand.position_id]
        day = day_of(work, snapshot.timezone)
        entries.append(ExportWork(
            assignment.employee_id, demand.id, work, work.name, position.name,
            position.function_id, position.workplace_id, assignment.fixed, "Einteilung", day,
            work.paid_minutes if snapshot.period_start <= day <= snapshot.period_end else 0,
        ))
    provenance = snapshot.metadata.get("provenance", {})
    # Optional descriptive metadata is not part of the work contract. Null or
    # non-mapping values carry no usable labels; keep the work and its exact ID.
    if not isinstance(provenance, Mapping):
        provenance = {}
    for work in snapshot.boundary_work:
        day = day_of(work, snapshot.timezone)
        in_period = snapshot.period_start <= day <= snapshot.period_end
        category = "Persönliche Arbeit" if in_period else "Randdienst"
        source = provenance.get(work.id, {})
        if not isinstance(source, Mapping):
            source = {}
        name = _provenance_text(source.get("name")) or category
        entries.append(ExportWork(
            work.employee_id, work.id, work, name, category if name != category else "",
            _provenance_text(source.get("function_id")), _provenance_workplace(source.get("workplace_id")), True,
            category, day, work.paid_minutes if in_period else 0,
        ))
    yield from _fit_provenance_names(snapshot, entries)
