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
