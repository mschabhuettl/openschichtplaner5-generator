"""Synthetic explicit-profile and context checks; no upstream limits inferred."""
from datetime import date, timedelta

import pytest

from sp5generator.models import RuleProfile
from tools.calendar_limits_candidate import diagnose_calendar
from tools.selected_work_segments_candidate import SelectedDuty
from tools.test_duty_conflicts_candidate import row

MON = date(2026, 1, 5)
WEEK = {MON + timedelta(days=i) for i in range(7)}


def profile(**changes):
    values = dict(id='p', valid_from=date(2025, 1, 1), valid_until=date(2027, 12, 31),
                  min_rest_minutes=660, confirmed=True)
    return RuleProfile(**(values | changes))


def report(rows=(), profiles=None, ids=('p',), start=MON, end=MON, covered=WEEK):
    return diagnose_calendar(rows, profiles if profiles is not None else [profile()],
                             ids, start, end, 'Europe/Vienna', covered)


def test_no_maximum_is_not_zero_or_inferred_from_rest():
    result = report([row('long', '08:00-08:00')])
    assert result.checks == ()
    assert not result.complete


def test_multiple_duties_sum_and_zero_is_a_real_limit():
    result = report([row('a', '08:00-12:00'), row('b', '16:00-20:00')],
                    [profile(max_daily_minutes=0)])
    assert [(c.observed_minutes, c.maximum_minutes, c.observed_exceeds)
            for c in result.checks] == [(480, 0, True)]


def test_exact_threshold_is_not_exceeded():
    result = report([row('a', '08:00-16:00')], [profile(max_daily_minutes=480)])
    assert not result.checks[0].observed_exceeds


def test_week_counts_context_outside_period_and_profile_validity():
    result = report([row('context', '08:00-16:00'),
                     row('plan', '08:00-16:00', MON + timedelta(days=2))],
                    [profile(valid_from=MON + timedelta(days=2), max_weekly_minutes=900)],
                    start=MON + timedelta(days=2), end=MON + timedelta(days=2))
    assert result.checks[0].observed_minutes == 960
    assert result.checks[0].observed_exceeds
    assert result.checks[0].missing_days == ()


def test_missing_week_days_are_not_certified_zero():
    result = report([], [profile(max_weekly_minutes=2400)], covered={MON})
    assert len(result.checks[0].missing_days) == 6
    assert 'calendar_context_incomplete' in result.unresolved
    assert not result.complete


def test_spill_activates_next_week_and_profile_with_all_context():
    sunday = MON + timedelta(days=6)
    monday = sunday + timedelta(days=1)
    result = report([row('plan', '20:00-08:00', sunday),
                     row('context', '10:00-12:00', monday)],
                    [profile(valid_until=sunday),
                     profile(id='next', valid_from=monday, max_daily_minutes=500,
                             max_weekly_minutes=550)],
                    ids=('p', 'next'), start=sunday, end=sunday,
                    covered=WEEK | {monday})
    assert [(c.code, c.observed_minutes, c.observed_exceeds) for c in result.checks] == [
        ('daily_limit', 600, True), ('weekly_limit', 600, True)]
    assert len(result.checks[1].missing_days) == 6


def test_unrelated_future_context_does_not_activate_limits():
    result = report([row('future', '00:00-24:00', MON + timedelta(days=7))],
                    [profile(max_daily_minutes=0, max_weekly_minutes=0)])
    assert all(not c.observed_exceeds for c in result.checks)


def test_unassigned_and_unconfirmed_profiles_not_silently_applied():
    result = report([row('a', '08:00-16:00')],
                    [profile(confirmed=False, max_daily_minutes=0),
                     profile(id='other', max_daily_minutes=0)], ids=('p', 'missing'))
    assert not result.checks
    assert {'profile_missing:missing', 'profile_unconfirmed:p',
            'profile_days_uncovered'} <= set(result.unresolved)


def test_multiple_confirmed_profiles_each_keep_their_limit():
    result = report([row('a', '08:00-16:00')],
                    [profile(max_daily_minutes=500), profile(id='q', max_daily_minutes=400)],
                    ids=('p', 'q'))
    assert [c.observed_exceeds for c in result.checks] == [False, True]


def test_replaced_missing_and_absence_rows_remain_honest():
    result = report([row('a', '08:00-16:00', issues=('absence_coexists_unresolved',)),
                     SelectedDuty('old', MON, 'replaced'),
                     SelectedDuty('missing', MON, 'unmeasurable')],
                    [profile(max_daily_minutes=600)])
    assert result.checks[0].observed_minutes == 480
    assert {'source:a', 'source:missing'} <= set(result.unresolved)
    assert 'source:old' not in result.unresolved
    assert not result.complete


@pytest.mark.parametrize(('day', 'minutes'), [(date(2026, 3, 29), 1380),
                                             (date(2026, 10, 25), 1500)])
def test_dst_uses_elapsed_daily_sum(day, minutes):
    result = report([row('dst', '00:00-24:00', day)],
                    [profile(max_daily_minutes=1440)], start=day, end=day, covered={day})
    assert result.checks[0].observed_minutes == minutes
    assert result.checks[0].observed_exceeds == (minutes > 1440)


def test_iso_year_boundary_has_separate_week_keys():
    sunday = date(2027, 1, 3)
    result = report([row('year', '20:00-08:00', sunday)],
                    [profile(max_weekly_minutes=400)], start=sunday, end=sunday)
    assert [(c.day.isocalendar()[:2], c.observed_minutes) for c in result.checks] == [
        ((2026, 53), 240), ((2027, 1), 480)]


def test_overlap_is_not_hidden_by_union():
    result = report([row('a', '08:00-16:00'), row('b', '08:00-16:00')],
                    [profile(max_daily_minutes=600)])
    assert result.checks[0].observed_minutes == 960
    assert 'other_rules_not_evaluated' in result.unresolved
    assert not result.complete


def test_duplicate_identities_fail():
    with pytest.raises(ValueError, match='Duty identities'):
        report([row('a', '08:00-16:00'), row('a', '08:00-16:00')])
    with pytest.raises(ValueError, match='Profile identities'):
        report(profiles=[profile(), profile()])


@pytest.mark.parametrize(('daily', 'weekly'), [(239, None), (240, 479),
                                              (240, 480), (None, None)])
def test_limit_findings_match_independent_generator_validator(daily, weekly):
    from test_calendar_limits import sample
    from sp5generator.models import Assignment
    from sp5generator.validator import validate
    from tools.work_segments_candidate import Duty, Segment

    snapshot = sample(MON)
    snapshot.profiles[0].max_daily_minutes = daily
    snapshot.profiles[0].max_weekly_minutes = weekly
    selected = [SelectedDuty(s.id, s.segments[0].start.date(), 'measured',
                             Duty(s.id, tuple(Segment(i.start, i.end) for i in s.segments)))
                for s in snapshot.shifts]
    observed = diagnose_calendar(selected, snapshot.profiles,
                                 snapshot.employees[0].profile_ids,
                                 snapshot.period_start, snapshot.period_end,
                                 snapshot.timezone, WEEK)
    validated = validate(snapshot, [Assignment(employee_id='e', demand_id=s.id)
                                    for s in snapshot.shifts])
    assert {(c.code, c.day) for c in observed.checks if c.observed_exceeds} == {
        (v.code, date.fromisoformat(v.date)) for v in validated.diagnostics
        if v.code in ('daily_limit', 'weekly_limit')}
