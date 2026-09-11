"""Pair diagnostics for selected measurable duties, never a completeness seal.

Reuses generator UTC/half-open interval helpers. A supplied daily rest threshold
is not a profile import; night exceptions, weekly rest and boundary coverage are
not evaluated here. Interleaving is reported separately from actual overlap.
"""
from dataclasses import dataclass
from itertools import combinations

from sp5generator.timeutils import bounds, overlap, segments


@dataclass(frozen=True)
class PairFinding:
    left: str
    right: str
    code: str
    minutes: int | None = None


@dataclass(frozen=True)
class PairReport:
    findings: tuple[PairFinding, ...]
    unresolved_sources: tuple[str, ...]
    complete: bool = False


def diagnose_pairs(selected, min_rest_minutes, *, planning_source_ids=None):
    """Inspect all pairs, including non-adjacent nested/duplicate duties.

    Replaced duties are intentionally inactive. Unmeasurable/absence-conflicted
    rows stay unresolved; measurable conflicted rows still contribute findings.
    Optional explicit planning identities restrict findings to pairs touching
    the plan. Context rows remain available, and their unresolved provenance
    remains reported. None retains the unrestricted audit; an empty set checks
    no planning pairs. Unknown identities are rejected, never silently ignored.
    No union, total, boundary inference or duty-length prohibition is made.
    """
    if type(min_rest_minutes) is not int or min_rest_minutes < 0:
        raise ValueError('Explicit nonnegative integer rest minutes required')
    selected = tuple(selected)
    if len({row.source_id for row in selected}) != len(selected):
        raise ValueError('Duty identities must be unique within the request')
    if planning_source_ids is not None:
        planning_source_ids = frozenset(planning_source_ids)
        if not planning_source_ids <= {row.source_id for row in selected}:
            raise ValueError('Planning identities must exist in selected sources')
    unresolved = tuple(row.source_id for row in selected
                       if row.status != 'replaced'
                       and (row.status != 'measured' or row.duty is None or row.issues))
    duties = [row.duty for row in selected
              if row.status == 'measured' and row.duty is not None]
    findings = []
    for left, right in combinations(sorted(duties, key=bounds), 2):
        if (planning_source_ids is not None
                and left.source_id not in planning_source_ids
                and right.source_id not in planning_source_ids):
            continue
        ls, rs = segments(left), segments(right)
        if any(overlap(a, b) for a in ls for b in rs):
            findings.append(PairFinding(left.source_id, right.source_id, 'overlap'))
            continue
        gap = bounds(right)[0] - bounds(left)[1]
        if gap < 0:
            findings.append(PairFinding(left.source_id, right.source_id, 'interleaving'))
        elif gap < min_rest_minutes:
            findings.append(PairFinding(left.source_id, right.source_id, 'rest', gap))
    return PairReport(tuple(findings), unresolved)
