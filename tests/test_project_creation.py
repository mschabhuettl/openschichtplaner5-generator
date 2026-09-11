"""Exercise standalone setup boundaries and actual generated planning semantics."""

from datetime import date

import pytest
from pydantic import ValidationError

from sp5generator.domain import input_diagnostics
from sp5generator.project_creation import ProjectCreateRequest, create_project
from sp5generator.solver import solve


def project_payload():
    return {
        'project_name': 'Projekt Alpha',
        'period_start': '2026-02-02', 'period_end': '2026-02-08', 'timezone': 'Europe/Vienna',
        'people': [{'name': f'Person {index}', 'weekly_hours': 16, 'employment_fraction': 50}
                   for index in range(3)],
        'positions': [{'name': 'Funktion A'}],
        'shift_templates': [{
            'name': 'Tagschicht', 'kind': 'day', 'start_time': '08:00', 'end_time': '16:00',
            'weekdays': [0, 1, 2, 3, 4], 'demands': [{'position': 0, 'minimum': 1, 'maximum': 1}],
        }],
        'rules': {'min_rest_hours': 11, 'after_night_rest_hours': 11,
                  'max_consecutive_work_days': 6, 'max_consecutive_nights': 3,
                  'max_daily_hours': 12, 'max_weekly_hours': 48, 'weekly_rest_hours': 36},
        'rules_confirmed': True, 'approvals_confirmed': True,
        'context_duty_free_confirmed': True,
    }


def build(payload):
    return create_project(ProjectCreateRequest.model_validate(payload))


def test_real_project_can_solve_and_preserves_individual_target_semantics():
    data = project_payload()
    data['people'][1] = {'name': 'Person Z', 'target_hours': 8, 'employment_fraction': 20}
    snapshot = build(data)
    assert snapshot.source == 'json'
    assert snapshot.metadata['project_name'] == 'Projekt Alpha'
    assert snapshot.employees[0].target_minutes == 16 * 60  # Already actual contract hours.
    assert snapshot.employees[1].target_minutes == 8 * 60
    assert len(snapshot.shifts) == 5
    assert not input_diagnostics(snapshot)
    result = solve(snapshot, time_limit=2)
    assert result.validation.valid and result.validation.complete
    assert len(result.assignments) == 5


def test_unconfirmed_approvals_and_context_stay_explicitly_incomplete():
    data = project_payload()
    data['approvals_confirmed'] = False
    data['context_duty_free_confirmed'] = False
    snapshot = build(data)
    assert not snapshot.context_complete
    assert all(not employee.approvals for employee in snapshot.employees)
    assert all(profile.confirmed for profile in snapshot.profiles)
    result = solve(snapshot, time_limit=1)
    assert not result.validation.complete


@pytest.mark.parametrize(('start', 'end', 'expected_minutes'), [
    ('2026-03-28', '2026-03-28', 7 * 60),
    ('2026-10-24', '2026-10-24', 9 * 60),
    ('2026-02-02', '2026-02-02', 8 * 60),
])
def test_overnight_templates_measure_elapsed_dst_minutes(start, end, expected_minutes):
    data = project_payload()
    data.update(period_start=start, period_end=end)
    data['shift_templates'][0].update(start_time='22:00', end_time='06:00', kind='night', weekdays=list(range(7)))
    snapshot = build(data)
    assert snapshot.shifts[0].paid_minutes == expected_minutes
    assert snapshot.shifts[0].segments[0].end.date() > snapshot.period_end
    assert not input_diagnostics(snapshot)


@pytest.mark.parametrize('day', ['2026-03-29', '2026-10-25'])
def test_dst_gap_and_fold_need_an_unambiguous_template(day):
    data = project_payload()
    data.update(period_start=day, period_end=day)
    data['shift_templates'][0].update(start_time='02:30', end_time='06:00', weekdays=[6])
    with pytest.raises(ValueError, match='Schicht „Tagschicht“'):
        build(data)


@pytest.mark.parametrize(('field', 'value'), [
    ('rules_confirmed', False), ('rules_confirmed', 'true'),
    ('approvals_confirmed', 1), ('context_duty_free_confirmed', 'false'),
    ('project_name', ' '), ('period_start', 0), ('period_start', '2026-02-02T00:00:00Z'),
    ('timezone', 'Missing/Zone'), ('period_end', '2025-01-01'), ('period_end', '2027-04-01'),
])
def test_setup_rejects_ambiguous_or_invalid_request_values(field, value):
    data = project_payload()
    data[field] = value
    with pytest.raises(ValidationError):
        build(data)


@pytest.mark.parametrize('patch', [
    {'weekly_hours': '40'}, {'weekly_hours': True}, {'weekly_hours': float('inf')},
    {'weekly_hours': -1}, {'weekly_hours': 169}, {'employment_fraction': 0},
    {'target_hours': 16},
])
def test_person_hours_must_be_finite_unambiguous_numbers(patch):
    data = project_payload()
    data['people'][0].update(patch)
    with pytest.raises(ValidationError):
        build(data)


@pytest.mark.parametrize('patch', [
    {'start_time': '24:00'}, {'start_time': '08:00:30'}, {'end_time': '08:00'},
    {'weekdays': [0, 0]}, {'weekdays': [True]}, {'weekdays': []},
    {'demands': [{'position': 1, 'minimum': 1, 'maximum': 1}]},
    {'demands': [{'position': 0, 'minimum': 2, 'maximum': 1}]},
    {'demands': [{'position': 0, 'minimum': 0, 'maximum': 0}]},
])
def test_shift_template_requires_valid_schedule_and_staffing(patch):
    data = project_payload()
    data['shift_templates'][0].update(patch)
    with pytest.raises(ValidationError):
        build(data)


@pytest.mark.parametrize(('field', 'value'), [
    ('min_rest_hours', 11.001), ('after_night_rest_hours', 11.001),
    ('weekly_rest_hours', 36.001), ('max_daily_hours', 12.009),
    ('max_weekly_hours', 48.009),
])
def test_rule_hours_are_never_silently_rounded(field, value):
    data = project_payload()
    data['rules'][field] = value
    with pytest.raises(ValueError, match='ganzen Minuten'):
        build(data)


@pytest.mark.parametrize(('hours', 'minutes'), [(11.25, 675), (6.1, 366), (1 / 60, 1)])
def test_minute_aligned_rules_are_preserved(hours, minutes):
    data = project_payload()
    for field in ('min_rest_hours', 'after_night_rest_hours', 'weekly_rest_hours',
                  'max_daily_hours', 'max_weekly_hours'):
        data['rules'][field] = hours
    profile = build(data).profiles[0]
    assert [profile.min_rest_minutes, profile.after_night_rest_minutes,
            profile.weekly_rest_minutes, profile.max_daily_minutes,
            profile.max_weekly_minutes] == [minutes] * 5


def test_api_explains_subminute_rules_without_creating_project(tmp_path):
    pytest.importorskip('fastapi')
    from fastapi.testclient import TestClient
    from sp5generator.webapp import create_app

    data = project_payload()
    data['rules']['min_rest_hours'] = 11.001
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        response = client.post('/api/projects/new', json=data)
        assert response.status_code == 422
        assert 'ganzen Minuten' in response.json()['detail']
        assert 'Projekt Alpha' not in response.text
        assert client.get('/api/snapshots').json() == []


def test_setup_budget_is_checked_before_expanding_shift_objects(monkeypatch):
    data = project_payload()
    data['shift_templates'][0]['demands'][0].update(minimum=1000, maximum=1000)
    data['shift_templates'][0]['weekdays'] = list(range(7))
    def unexpected_localize(*args):
        pytest.fail('Expansion happened before checking the minimum-assignment budget')
    monkeypatch.setattr('sp5generator.project_creation.localize', unexpected_localize)
    with pytest.raises(ValueError, match='Planungsgröße'):
        build(data)


def test_no_occurrences_and_date_overflow_fail_cleanly():
    data = project_payload()
    data.update(period_start='2026-02-08', period_end='2026-02-08')
    with pytest.raises(ValueError, match='keine Schicht'):
        build(data)
    data.update(period_start='0001-01-01', period_end='0001-01-07')
    with pytest.raises(ValueError, match='Datumsbereichs'):
        build(data)


def test_context_margin_follows_long_consecutive_day_rules():
    data = project_payload()
    data['rules']['max_consecutive_work_days'] = 20
    snapshot = build(data)
    assert (snapshot.period_start - snapshot.context_start).days == 20
    assert (snapshot.context_end - snapshot.period_end).days == 20
    assert snapshot.profiles[0].valid_from == date(2026, 1, 13)


def test_project_factory_api_creates_then_allows_normal_save(tmp_path):
    pytest.importorskip('fastapi')
    from fastapi.testclient import TestClient
    from sp5generator.webapp import create_app

    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        response = client.post('/api/projects/new', json=project_payload())
        assert response.status_code == 200, response.text
        snapshot = response.json()['snapshot']
        assert snapshot['revision'] == '0'
        assert client.get('/api/snapshots/' + snapshot['id']).status_code == 404
        saved = client.put('/api/snapshots', json=snapshot)
        assert saved.status_code == 200
        assert saved.json()['revision'] == '1'
        data = project_payload()
        data['rules_confirmed'] = False
        assert client.post('/api/projects/new', json=data).status_code == 422


def test_new_setup_defaults_and_explicit_weekly_rest_are_distinct():
    payload = project_payload()
    del payload['rules']['weekly_rest_hours']
    created = build(payload)
    assert created.profiles[0].min_rest_minutes == 660
    assert created.profiles[0].weekly_rest_minutes == 2160
    assert created.profiles[0].weekly_rest_frame == 'calendar_week'
    assert not created.profiles[0].weekly_rest_add_daily
    assert created.objectives.workday_transitions == 100
    payload['rules']['weekly_rest_hours'] = 48
    assert build(payload).profiles[0].weekly_rest_minutes == 2880
