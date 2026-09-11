"""Synthetic characterization of upstream cycle generation, never API writes."""
from sp5lib import database
import pytest


def run_cycle(monkeypatch, tmp_path, weekly=8, existing_day=None, duration=8):
    monkeypatch.setattr(database._paths, 'api_data_dir', lambda: str(tmp_path))
    rows = {
        'CYCLE': [{'ID': 1, 'SIZE': 31, 'UNIT': 0}],
        'CYENT': [{'CYCLEEID': 1, 'INDEX': 0, 'SHIFTID': 1}],
        'EMPL': [{'ID': 1, 'CALCBASE': 2, 'HRSMONTH': 160, 'HRSWEEK': weekly}],
        'SHIFT': [{'ID': 1, **{f'DURATION{i}': duration for i in range(8)},
                   **{f'STARTEND{i}': '00:00-24:00' for i in range(8)}}],
        'MASHI': [] if existing_day is None else [
            {'EMPLOYEEID': 1, 'DATE': existing_day, 'SHIFTID': 1}],
    }
    db = object.__new__(database.SP5Database)
    db._read = lambda table: rows.get(table, [])
    db.get_cycle_assignments = lambda: [
        {'employee_id': 1, 'cycle_id': 1, 'start': '2026-09-02'}]
    db.add_schedule_entry = lambda *args: pytest.fail('characterization must not write')
    return db.generate_schedule_from_cycle(2026, 9, dry_run=True)


@pytest.mark.parametrize('weekly,created', [(7, 0), (8, 1), (0, 1)])
def test_cycle_uses_hrsweek_even_for_monthly_calcbase(monkeypatch, tmp_path, weekly, created):
    result = run_cycle(monkeypatch, tmp_path, weekly=weekly)
    assert result['errors'] == []
    assert result['created'] == created
    assert result['skipped_hours_limit'] == 1 - created


@pytest.mark.parametrize('existing_day,created', [('2026-08-31', 1), ('2026-09-01', 0)])
def test_cycle_week_tracker_drops_previous_month_same_iso_week(monkeypatch, tmp_path, existing_day, created):
    # Both context dates share ISO week 36 with Wednesday September 2.
    result = run_cycle(monkeypatch, tmp_path, existing_day=existing_day)
    assert result['errors'] == []
    assert result['created'] == created
    assert result['skipped_hours_limit'] == 1 - created


def test_cycle_limit_counts_duration_not_startend_elapsed(monkeypatch, tmp_path):
    result = run_cycle(monkeypatch, tmp_path, weekly=8, duration=8)
    assert result['created'] == 1  # STARTEND says 24 hours, DURATION credits eight.
    assert result['report']['employees'][0]['max_weekly_hours_planned'] == 8
