"""Synthetic cross-duty checks; no personal rules or source data inferred."""
from datetime import date

import pytest

from tools.duty_conflicts_candidate import diagnose_pairs
from tools.selected_work_segments_candidate import SelectedDuty
from tools.work_segments_candidate import measure_duty


def row(identity, windows, day=date(2026, 1, 5), issues=()):
    return SelectedDuty(identity, day, 'measured',
                        measure_duty(identity, day, windows, 'Europe/Vienna'), issues)


def test_duplicate_and_nested_duties_are_not_lost_by_adjacent_scan():
    report = diagnose_pairs([row('long', '08:00-20:00'), row('inner', '09:00-10:00'),
                             row('later', '11:00-12:00')], 0)
    assert {(f.left, f.right, f.code) for f in report.findings} == {
        ('long', 'inner', 'overlap'), ('long', 'later', 'overlap')}
    duplicate = diagnose_pairs([row('a', '08:00-16:00'), row('b', '08:00-16:00')], 0)
    assert duplicate.findings[0].code == 'overlap'


def test_split_gap_is_interleaving_not_actual_work_overlap():
    report = diagnose_pairs([row('split', '08:00-12:00 16:00-20:00'),
                             row('inside-gap', '13:00-15:00')], 660)
    assert [f.code for f in report.findings] == ['interleaving']
    assert not diagnose_pairs([row('split', '08:00-12:00 16:00-20:00')], 660).findings


@pytest.mark.parametrize(('required', 'codes'), [(0, []), (660, ['rest'])])
def test_touching_duties_have_zero_rest_not_overlap(required, codes):
    report = diagnose_pairs([row('a', '08:00-12:00'), row('b', '12:00-16:00')], required)
    assert [f.code for f in report.findings] == codes
    if codes:
        assert report.findings[0].minutes == 0


@pytest.mark.parametrize(('month', 'day', 'start', 'expected'),
                         [(3, 29, '07:00', 600), (10, 25, '06:00', None)])
def test_rest_across_dst_is_elapsed_not_wall_clock(month, day, start, expected):
    report = diagnose_pairs([
        row('a', '12:00-20:00', date(2026, month, day - 1)),
        row('b', f'{start}-12:00', date(2026, month, day))], 660)
    assert [f.minutes for f in report.findings] == ([] if expected is None else [expected])


def test_replaced_excluded_missing_and_absence_preserved_without_seal():
    selected = [row('a', '08:00-16:00', issues=('absence_coexists_unresolved',)),
                SelectedDuty('missing', date(2026, 1, 5), 'unmeasurable'),
                SelectedDuty('old', date(2026, 1, 5), 'replaced')]
    report = diagnose_pairs(selected, 660)
    assert report.unresolved_sources == ('a', 'missing')
    assert not report.findings
    assert report.complete is False
    assert diagnose_pairs([], 660).complete is False


def test_24h_duty_is_not_automatically_a_violation_and_exact_rest_passes():
    report = diagnose_pairs([row('a', '08:00-08:00'),
                             row('b', '19:00-23:00', date(2026, 1, 6))], 660)
    assert not report.findings


@pytest.mark.parametrize('invalid', [-1, None, 11.0, True])
def test_invalid_rest_threshold_rejected(invalid):
    with pytest.raises(ValueError):
        diagnose_pairs([], invalid)


def test_duplicate_identity_rejected():
    with pytest.raises(ValueError, match='identities'):
        diagnose_pairs([row('same', '08:00-12:00'), row('same', '16:00-20:00')], 660)
