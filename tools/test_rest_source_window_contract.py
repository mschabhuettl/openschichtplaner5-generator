"""Calendar selector envelopes are not sufficient daily-rest source horizons.

Synthetic native one-night duties only; no assertion of source completeness.
"""
from datetime import date, timedelta

import pytest

from tools.calendar_limits_candidate import calendar_source_window
from tools.duty_conflicts_candidate import diagnose_pairs
from tools.test_duty_conflicts_candidate import row


@pytest.mark.parametrize('weekly', [False, True])
@pytest.mark.parametrize('side', ['before', 'after'])
def test_calendar_envelope_can_hide_seven_hour_boundary_rest(weekly, side):
    monday = date(2026, 1, 5)
    day = monday if side == 'before' else monday + timedelta(days=6)
    if side == 'before':
        # Starts two dates before the checked day, ends Sunday at 23:00.
        # One preceding source date covers incoming calendar work, not rest.
        duties = [row('context', '23:00-23:00', day - timedelta(days=2)),
                  row('planning', '06:00-14:00', day)]
    else:
        # No planning spill: Monday work still constrains Sunday's daily rest.
        duties = [row('planning', '15:00-23:00', day),
                  row('context', '06:00-14:00', day + timedelta(days=1))]
    window = calendar_source_window([day], weekly=weekly)
    loaded = [d for d in duties if window.source_start <= d.day <= window.source_end]
    assert len(loaded) == 1
    limited = diagnose_pairs(loaded, 660)
    full = diagnose_pairs(duties, 660)
    assert limited.findings == ()
    assert [(f.code, f.minutes) for f in full.findings] == [('rest', 420)]
    # Neither an empty finding list nor the larger fixture proves DB coverage.
    assert not limited.complete
    assert not full.complete


def test_planning_scope_keeps_boundary_pairs_but_not_context_only_conflicts():
    duties = [row('old-a', '08:00-16:00', date(2026, 1, 2)),
              row('old-b', '09:00-17:00', date(2026, 1, 2)),
              row('before', '15:00-23:00', date(2026, 1, 4)),
              row('plan', '06:00-14:00', date(2026, 1, 5)),
              row('after', '20:00-23:00', date(2026, 1, 5))]
    report = diagnose_pairs(duties, 660, planning_source_ids={'plan'})
    assert [(f.left, f.right, f.minutes) for f in report.findings] == [
        ('before', 'plan', 420), ('plan', 'after', 360)]
    assert 'overlap' in {f.code for f in diagnose_pairs(duties, 660).findings}
    assert not diagnose_pairs(duties, 660, planning_source_ids=set()).findings
    assert not report.complete


def test_planning_scope_does_not_hide_unresolved_context():
    duties = [row('plan', '06:00-14:00'),
              row('context', '20:00-23:00', issues=('source_unresolved',))]
    report = diagnose_pairs(duties, 660, planning_source_ids={'plan'})
    assert report.unresolved_sources == ('context',)
    assert len(report.findings) == 1
    assert not report.complete


def test_unknown_planning_identity_is_not_silently_a_clean_plan():
    with pytest.raises(ValueError, match='Planning identities'):
        diagnose_pairs([row('plan', '06:00-14:00')], 660,
                       planning_source_ids={'typo'})


@pytest.mark.parametrize('profile_day', [5, 6])
@pytest.mark.parametrize('assigned', [False, True])
def test_dated_rest_at_either_start_requires_assigned_profile(profile_day, assigned):
    """A request-wide 11h scalar cannot replace dated personal rules."""
    from sp5generator.domain import pair_conflict
    from sp5generator.solver import solve
    from sp5generator.validator import validate
    from test_core_rules import assignment, case, shift

    snapshot = case(1, [shift('a', 5, 8, 8), shift('b', 6, 8, 8)])
    snapshot.profiles[0].min_rest_minutes = 660
    extra = snapshot.profiles[0].model_copy(update={
        'id': 'dated', 'valid_from': date(2026, 1, profile_day),
        'valid_until': date(2026, 1, profile_day), 'min_rest_minutes': 17 * 60,
    })
    snapshot.profiles.append(extra)
    if assigned:
        snapshot.employees[0].profile_ids.append(extra.id)
    # 16h elapsed rest passes 11h but fails the assigned 17h rule at either start.
    selected = [row('a', '08:00-16:00', date(2026, 1, 5)),
                row('b', '08:00-16:00', date(2026, 1, 6))]
    assert not diagnose_pairs(selected, 660).findings
    assert pair_conflict(snapshot, snapshot.employees[0], *snapshot.shifts) == (
        'rest' if assigned else None)
    checked = validate(snapshot, [assignment(d='a'), assignment(d='b')])
    assert checked.valid is (not assigned)
    result = solve(snapshot, 3, partial=True)
    assert result.solver_status == 'OPTIMAL'
    assert len(result.assignments) == (1 if assigned else 2)
    assert result.validation.valid


@pytest.mark.parametrize('bridge', [False, True])
def test_night_block_context_depends_on_selected_bridge_not_arbitrary_pairs(bridge):
    from sp5generator.domain import night_block_conflict, pair_conflict
    from sp5generator.solver import solve
    from sp5generator.validator import validate
    from test_core_rules import assignment, case, shift

    snapshot = case(1, [shift('a', 5, 22, 8, 'night'),
                        shift('b', 6, 22, 8, 'night'),
                        shift('c', 7, 22, 8, 'night')])
    snapshot.profiles[0].min_rest_minutes = 660
    snapshot.profiles[0].after_night_block_rest_minutes = 2880
    employee = snapshot.employees[0]
    left, middle, right = snapshot.shifts
    assert pair_conflict(snapshot, employee, left, right) is None
    assert night_block_conflict(snapshot, employee, left, right)
    assert not night_block_conflict(snapshot, employee, left, middle)
    assert not night_block_conflict(snapshot, employee, middle, right)
    selected = [row('a', '22:00-06:00', date(2026, 1, 5)),
                row('c', '22:00-06:00', date(2026, 1, 7))]
    if bridge:
        selected.append(row('b', '22:00-06:00', date(2026, 1, 6)))
    else:
        snapshot.demands[1].minimum = snapshot.demands[1].maximum = 0
    report = diagnose_pairs(selected, 660)
    assert not report.findings and not report.complete
    checked = validate(snapshot, [assignment(d=item.source_id) for item in selected])
    assert checked.valid is bridge
    result = solve(snapshot, 3, partial=True)
    assert result.solver_status == 'OPTIMAL'
    assert len(result.assignments) == (3 if bridge else 1)
    assert result.validation.valid


@pytest.mark.parametrize('assigned', [False, True])
@pytest.mark.parametrize('profile_day', [5, 6, 7])
def test_exhaustive_selected_nights_cannot_bridge_dated_daily_rest(assigned, profile_day):
    """Check every subset against an explicit fixture oracle, not solver output."""
    from itertools import combinations

    from sp5generator.solver import solve
    from sp5generator.validator import validate
    from test_core_rules import assignment, case, shift

    snapshot = case(1, [shift(name, day, 22, 8, 'night')
                        for name, day in [('a', 5), ('b', 6), ('c', 7)]])
    snapshot.profiles[0].min_rest_minutes = 660
    snapshot.profiles[0].after_night_block_rest_minutes = 2880
    snapshot.profiles.append(snapshot.profiles[0].model_copy(update={
        'id': 'dated', 'valid_from': date(2026, 1, profile_day),
        'valid_until': date(2026, 1, profile_day), 'min_rest_minutes': 1020,
    }))
    if assigned:
        snapshot.employees[0].profile_ids.append('dated')
    # Adjacent nights have 16h rest; separated outer nights have 40h.
    # All three bridge the 48h block rule, but never an assigned 17h daily rule.
    allowed = {frozenset(), frozenset('a'), frozenset('b'), frozenset('c')}
    if not assigned or profile_day == 7:
        allowed.add(frozenset('ab'))
    if not assigned or profile_day == 5:
        allowed.add(frozenset('bc'))
    if not assigned:
        allowed.add(frozenset('abc'))
    for size in range(4):
        for subset in combinations('abc', size):
            checked = validate(snapshot, [assignment(d=name) for name in subset])
            assert checked.valid is (frozenset(subset) in allowed), subset
    result = solve(snapshot, 3, partial=True)
    assert result.solver_status == 'OPTIMAL'
    selected = frozenset(a.demand_id for a in result.assignments)
    assert selected in allowed
    assert len(selected) == max(map(len, allowed))
    assert result.validation.valid
