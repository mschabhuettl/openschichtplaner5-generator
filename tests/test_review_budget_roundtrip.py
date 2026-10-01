"""Two independent admission ceilings; real HTTP/SQLite/CLI lifecycle proofs.

All data is synthetic. Unit counts are independently calculated, not taken from
production guards. Sparse acceptance deliberately changes under this policy.
"""
from collections.abc import Mapping
from copy import deepcopy
import json
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, TypeAdapter, ValidationError

from sp5generator.models import Snapshot
from sp5generator.webapp import PlanRequest, ReplacementRequest, create_app


def fixture():
    return {
        'id': 'review-synthetic', 'revision': '1', 'created_at': '2026-01-01T00:00:00Z',
        'timezone': 'UTC', 'period_start': '2026-01-05', 'period_end': '2026-01-05',
        'context_start': '2025-12-22', 'context_end': '2026-01-19', 'context_complete': True,
        'rule_version': 'synthetic-only', 'source': 'synthetic', 'software_versions': {},
        'employees': [{'id': 'p', 'name': 'Synthetic person', 'team_ids': ['team'],
                       'employment_start': '2025-12-22', 'employment_end': '2026-01-19',
                       'profile_ids': ['rule'], 'approvals': [{'function_id': 'role', 'workplace_id': 'unit',
                       'valid_from': '2025-12-22', 'valid_until': '2026-01-19'}]}],
        'positions': [{'id': 'pos', 'name': 'Synthetic position', 'function_id': 'role',
                       'workplace_id': 'unit', 'qualifications_required': False}],
        'profiles': [{'id': 'rule', 'valid_from': '2025-12-22', 'valid_until': '2026-01-19',
                      'min_rest_minutes': 0, 'confirmed': True}],
        'shifts': [{'id': 'duty', 'name': 'Synthetic duty', 'kind': 'day', 'team_id': 'team',
                    'segments': [{'start': '2026-01-05T08:00:00Z', 'end': '2026-01-05T09:00:00Z'}],
                    'paid_minutes': 60}],
        'demands': [{'id': 'need', 'shift_id': 'duty', 'position_id': 'pos', 'minimum': 1, 'maximum': 1}],
        'assignments': [], 'wishes': [], 'metadata': {},
    }


def units(value, request=False):
    exemption = ('snapshot', 'metadata') if request else ('metadata',)

    def count(item, path):
        if path == exemption:
            return 0
        if isinstance(item, BaseModel):
            pairs = list(vars(item).items()) + list((item.__pydantic_extra__ or {}).items())
        elif isinstance(item, Mapping):
            pairs = item.items()
        elif isinstance(item, (list, tuple)):
            pairs = enumerate(item)
        else:
            return 0
        return sum(1 + count(child, path + (key,)) for key, child in pairs)
    return 1 + count(value, ())


def padded(target, canonical=True):
    data = Snapshot.model_validate(fixture()).model_dump(mode='json') if canonical else fixture()
    data['software_versions'].update({f'v{i}': '1' for i in range(target - units(data))})
    assert units(data) == target
    return data


def sparse(approvals):
    data = fixture()
    template = data['employees'][0]
    template['approvals'].extend(dict(template['approvals'][0], function_id=f'extra-role-{i}')
                                 for i in range(approvals - 1))
    data['employees'] = [dict(deepcopy(template), id=f'person{i}') for i in range(1000)]
    return data


def db_state(store):
    with store.connect() as conn:
        return {table: [dict(row) for row in conn.execute(f'SELECT * FROM {table} ORDER BY rowid')]
                for table in ('snapshots', 'jobs', 'accepted', 'receipts', 'audit')}


@pytest.fixture
def exchange(tmp_path):
    app = create_app(str(tmp_path), start_worker=False)
    with TestClient(app) as client:
        yield app.state.store, client


@pytest.mark.parametrize('shape', ['exact-raw', 'sparse-four'])
@pytest.mark.parametrize('operation', ['check', 'new-save', 'overwrite'])
def test_normalized_overflow_rejected_before_acknowledgement(exchange, shape, operation):
    store, client = exchange
    if operation == 'overwrite':
        assert client.put('/api/snapshots', json=fixture()).status_code == 200
        assert client.post('/api/jobs', json={'snapshot_id': 'review-synthetic', 'time_limit': 1}).status_code == 200
    data = padded(50000, False) if shape == 'exact-raw' else sparse(4)
    assert units(data) == (50000 if shape == 'exact-raw' else 30049)
    before = db_state(store)
    response = (client.post('/api/snapshots/check', json=data) if operation == 'check'
                else client.put('/api/snapshots', json=data))
    assert response.status_code == 422
    assert len(response.content) < 4096
    assert db_state(store) == before


@pytest.mark.parametrize('parse', [Snapshot.model_validate, TypeAdapter(Snapshot).validate_python,
                                  lambda data: Snapshot(**data),
                                  lambda data: Snapshot.model_validate_json(json.dumps(data))])
def test_all_parsers_apply_normalized_guard(parse):
    with pytest.raises(ValidationError, match=r'\[size_limit\]') as failure:
        parse(padded(50000, False))
    assert failure.value.error_count() == 1


@pytest.mark.parametrize('cls', [PlanRequest, ReplacementRequest])
def test_request_normalized_ceiling_and_instance_replay(cls):
    data = {'snapshot': padded(49995 if cls is PlanRequest else 49992),
            'assignments': [{'employee_id': 'p', 'demand_id': 'need'}]}
    if cls is ReplacementRequest:
        data.update(employee_id='p', absent_from='2026-01-05', absent_until='2026-01-05')
    assert units(data, True) == 50000
    with pytest.raises(ValidationError, match=r'\[size_limit\]'):
        cls.model_validate(data)
    # Removing two units offsets the real Assignment defaults, no default table.
    for key in list(data['snapshot']['software_versions'])[-2:]:
        del data['snapshot']['software_versions'][key]
    value = cls.model_validate(data)
    assert units(value, True) == 50000
    assert cls.model_validate_json(value.model_dump_json()) == value
    value.snapshot.software_versions['one-more'] = '1'
    with pytest.raises(ValidationError, match=r'\[size_limit\]'):
        cls.model_validate(value)


@pytest.mark.parametrize('shape', ['canonical-exact', 'sparse-two'])
def test_accepted_lifecycle_and_actual_cli_worker(exchange, tmp_path, shape):
    store, client = exchange
    data = padded(50000) if shape == 'canonical-exact' else sparse(2)
    model = Snapshot.model_validate(data)
    assert units(model) == (50000 if shape == 'canonical-exact' else 43090)
    assert Snapshot.model_validate_json(model.model_dump_json()) == model
    checked = client.post('/api/snapshots/check', json=data)
    assert checked.status_code == 200
    saved = client.put('/api/snapshots', json=checked.json())
    assert saved.status_code == 200
    assert client.get('/api/snapshots/' + data['id']).json() == saved.json()
    copied = client.post('/api/snapshots/' + data['id'] + '/copy', json={'revision': saved.json()['revision']})
    assert copied.status_code == 200
    assert client.get('/api/snapshots/' + copied.json()['id']).json() == copied.json()
    archived = client.post('/api/snapshots/' + data['id'] + '/archive', json={'revision': saved.json()['revision']})
    assert archived.status_code == 200
    restored = client.post('/api/snapshots/' + data['id'] + '/restore', json={'revision': archived.json()['revision']})
    assert restored.status_code == 200
    assert client.get('/api/snapshots/' + data['id']).json() == restored.json()
    job = client.post('/api/jobs', json={'snapshot_id': data['id'], 'snapshot_revision': restored.json()['revision'], 'time_limit': 2})
    assert job.status_code == 200
    assert client.get('/api/jobs/' + job.json()['id'] + '/snapshot').json() == restored.json()
    command = [sys.executable, '-m', 'sp5generator.cli', 'worker', '--store', store.path, '--once']
    worker = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (tmp_path / 'worker.log').write_text(worker.stdout + worker.stderr)
    (tmp_path / 'worker-command.json').write_text(json.dumps({'command': command, 'exit_code': worker.returncode}))
    assert worker.returncode == 0
    result = client.get('/api/jobs/' + job.json()['id']).json()
    assert result['state'] == 'succeeded', result
    assert result['result']['validation']['valid']
    assert json.loads(db_state(store)['snapshots'][0]['payload']) == restored.json()


def test_snapshot_limit_is_not_request_envelope_limit(exchange):
    _, client = exchange
    data = padded(50000)
    assert client.post('/api/snapshots/check', json=data).status_code == 200
    assert units({'snapshot': data, 'assignments': []}, True) == 50002
    assert client.post('/api/validate', json={'snapshot': data, 'assignments': []}).status_code == 422
