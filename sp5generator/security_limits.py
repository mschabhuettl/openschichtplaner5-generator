"""Bound diagnostic presentation without changing planning decisions or IDs."""
from collections import Counter
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from itertools import chain
import json
from io import StringIO

MAX_PLANNING_PARSE_UNITS = 50_000
MAX_SNAPSHOT_BYTES = 16 * 1024 * 1024

MAX_DIAGNOSTICS = 100
MAX_DIAGNOSTIC_BYTES = 48 * 1024  # Leave room for envelope and exact code counts.
MAX_DIAGNOSTIC_WORK_ITEMS = 10_000
MAX_DIAGNOSTIC_WORK_CHARACTERS = 1_000_000
_diagnostic_work: ContextVar[list[int] | None] = ContextVar('diagnostic_work', default=None)


def bounded_planning_records(value, *, request=False):
    """Bound parse work before Pydantic expands fields into errors.

    Charge one root unit, then one per mapping entry or sequence slot, including
    scalars and empty containers. A container is not charged again on descent.
    The 50,000-unit ceiling includes unknown keys and parsed model fields.
    Only the snapshot's own metadata contents are exempt; its entry still costs
    one unit. With request=True, that snapshot is the root's 'snapshot' member;
    all other request fields (including external assignments) share the budget.
    Visit occurrences, not unique objects, to charge repeated parsing work.
    """
    from pydantic import BaseModel

    def children(item, scope):
        if isinstance(item, BaseModel):
            # No model_dump, recursive copy or materialized list of entries.
            entries = chain(item.__dict__.items(), (item.__pydantic_extra__ or {}).items())
        elif isinstance(item, Mapping):
            entries = item.items()
        elif isinstance(item, (list, tuple)):
            for child in item:
                yield child, None
            return
        else:
            return
        for key, child in entries:
            if scope == 'snapshot' and key == 'metadata':
                child_scope = 'metadata'
            elif scope == 'request' and key == 'snapshot':
                child_scope = 'snapshot'
            else:
                child_scope = None
            yield child, child_scope

    count = 0
    stack: list[Iterator] = [iter(((value, 'request' if request else 'snapshot'),))]
    while stack:
        try:
            item, scope = next(stack[-1])
        except StopIteration:
            stack.pop()
            continue
        count += 1
        if count > MAX_PLANNING_PARSE_UNITS:
            raise ValueError('Zu viele Planungseingaben (Parsebudget: 50000 Einheiten) [size_limit]')
        if scope != 'metadata':
            stack.append(children(item, scope))
    return value


class PlanningBudgetExceeded(ValueError):
    """The normalized planning value is too large for a safe handoff."""


def bounded_normalized_planning(value, *, request=False):
    """Check actual default-expanded fields, independently of the raw budget.

    Also use at native handoffs: identity, mutation and model_copy are not
    certificates. This guard deliberately does not serialize optional metadata.
    """
    try:
        return bounded_planning_records(value, request=request)
    except ValueError:
        raise PlanningBudgetExceeded(
            'Zu viele verschachtelte Planungsdatensätze oder Planungsfelder '
            '(normalisiertes Budget: 50000 Einheiten) [size_limit]'
        ) from None


class SnapshotWireError(ValueError):
    """No source values in serialization/encoding failures."""

    def __init__(self):
        super().__init__('Projekt ist nicht verlustfrei als kanonisches UTF-8-JSON darstellbar [wire_format]')


class SnapshotWireSizeExceeded(SnapshotWireError):
    def __init__(self):
        ValueError.__init__(self, 'Kanonisches Projekt überschreitet die Grenze von 16 MiB [wire_size_limit]')


def bounded_canonical_json(value):
    """Strict compact UTF-8 JSON, using the same byte ceiling as HTTP input.

    Reject non-JSON native metadata rather than stringify/coerce it. The
    iterative type check handles cycles without recursion or an unbounded copy;
    its occurrence ceiling is a lower bound on JSON bytes, not planning units.
    Encoding is streamed into a bounded buffer, including escapes and UTF-8.
    """
    def entries(item):
        for key, child in item.items():
            if type(key) is not str:
                raise SnapshotWireError()
            yield key
            yield child

    stack: list[tuple[Iterator, int | None]] = [(iter((value,)), None)]
    active = set()
    occurrences = 0
    while stack:
        try:
            item = next(stack[-1][0])
        except StopIteration:
            _, identity = stack.pop()
            active.discard(identity)
            continue
        occurrences += 1
        if occurrences > MAX_SNAPSHOT_BYTES:
            raise SnapshotWireSizeExceeded()
        if type(item) in (dict, list):
            identity = id(item)
            if identity in active:
                raise SnapshotWireError()
            active.add(identity)
            stack.append((entries(item) if type(item) is dict else iter(item), identity))
        elif type(item) not in (str, int, float, bool, type(None)):
            raise SnapshotWireError()
        elif isinstance(item, str) and len(item) > MAX_SNAPSHOT_BYTES:
            raise SnapshotWireSizeExceeded()
    try:
        output = StringIO()
        size = 0
        encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False, separators=(',', ':'))
        for chunk in encoder.iterencode(value):
            size += len(chunk.encode('utf-8'))
            if size > MAX_SNAPSHOT_BYTES:
                raise SnapshotWireSizeExceeded()
            output.write(chunk)
        return output.getvalue()
    except SnapshotWireError:
        raise
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise SnapshotWireError() from None


class DiagnosticBudgetExceeded(RuntimeError):
    """Abort the entire operation; a partial check must never be called valid."""


@contextmanager
def diagnostic_budget():
    """Share nested work in one operation, but isolate requests and reset errors."""
    if _diagnostic_work.get() is not None:
        yield
        return
    token = _diagnostic_work.set([0, 0])
    try:
        yield
    finally:
        _diagnostic_work.reset(token)


def charge_diagnostic(value):
    """Stop repeated diagnostic construction, not just final serialization.

    Input model collection/ID limits bound each expansion before this hook;
    this cumulative budget also covers quadratic validator conflict reports.
    RuntimeError intentionally bypasses domain's invalid-input ValueError catch.
    """
    work = _diagnostic_work.get()
    if work is not None and isinstance(value, dict):
        work[0] += 1
        work[1] += sum(len(v) for v in value.values() if isinstance(v, str))
        if work[0] > MAX_DIAGNOSTIC_WORK_ITEMS or work[1] > MAX_DIAGNOSTIC_WORK_CHARACTERS:
            raise DiagnosticBudgetExceeded('Diagnostic construction budget exceeded')
    return value


def validation_error_report(errors):
    """Never echo inputs/context, including untrusted dictionary keys in loc."""
    fields = []
    used = 0
    for error in errors[:MAX_DIAGNOSTICS]:
        location = [
            part if isinstance(part, int) or (isinstance(part, str) and len(part) <= 200)
            else '[overlong field name]'
            for part in error['loc'][:16]
        ]
        field = {'location': location, 'type': error['type']}
        size = len(json.dumps(field, ensure_ascii=False).encode('utf-8'))
        if used + size > MAX_DIAGNOSTIC_BYTES:
            break
        fields.append(field)
        used += size
    return {
        'detail': 'Ungültige Eingabe. Feldtypen und Pflichtangaben anhand des Eingabeschemas prüfen.',
        'fields': fields,
        'fields_total': len(errors),
        'fields_omitted': len(errors) - len(fields),
    }


def diagnostic_report(issues):
    """Keep full-result status/counts separate from its bounded presentation.

    Omit entire records rather than truncating identifiers or messages. The
    caller must derive ready/valid/complete from the full, unmodified result.
    """
    shown = []
    used = 0
    # Staffing/context incompleteness must not crowd later personal violations
    # out of the visible sample. Validation flags still use the entire report.
    ordered = sorted(issues, key=lambda issue: issue.code in {'vacancy', 'context'})
    for issue in ordered:
        if len(shown) == MAX_DIAGNOSTICS:
            break
        # Omit an oversized record, but still consider later smaller records.
        # Avoid serializing a single oversized message just to measure it.
        if sum(len(v) for v in issue.__dict__.values() if isinstance(v, str)) > MAX_DIAGNOSTIC_BYTES:
            continue
        value = issue.model_dump(mode="json")
        size = len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) + 1
        if used + size > MAX_DIAGNOSTIC_BYTES:
            continue
        used += size
        shown.append(value)
    return {
        "diagnostics": shown,
        "diagnostics_total": len(issues),
        "diagnostics_omitted": len(issues) - len(shown),
        "diagnostics_by_code": dict(Counter(issue.code for issue in issues)),
    }
