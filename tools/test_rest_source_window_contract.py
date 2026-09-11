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
