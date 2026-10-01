"""Canonical wire admission is separate from native optional export metadata."""
from copy import deepcopy
from datetime import date
import json

import pytest

from sp5generator.jobs import Store
from sp5generator.models import Snapshot
from test_review_budget_roundtrip import db_state, fixture, padded, sparse
from test_review_budget_roundtrip import exchange as exchange

LIMIT = 16 * 1024 * 1024


def compact(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')


def at_bytes(size, *, canonical=True, text='x'):
    data = Snapshot.model_validate(fixture()).model_dump(mode='json') if canonical else fixture()
    data['metadata'] = {'opaque': '', 'exact': {'Unicode': '𐐀ä', 'escaped': '\n"\\\t', 'value': [None, True, 1.25]}}
    space = size - len(compact(data))
    width = len(compact(text)) - 2
    data['metadata']['opaque'] = text * (space // width) + 'x' * (space % width)
    assert len(compact(data)) == size
    return data


@pytest.mark.parametrize('offset', [-1, 0, 1])
@pytest.mark.parametrize('text', ['x', '💡', '\n'])
def test_exact_canonical_wire_bound_store_and_http(exchange, offset, text):
    store, client = exchange
    snapshot = Snapshot.model_validate(at_bytes(LIMIT + offset, text=text))
    before = db_state(store)
    if offset > 0:
        with pytest.raises(ValueError, match=r'16 MiB|wire_size_limit'):
            store.save_snapshot(snapshot, 'local-user')
        assert db_state(store) == before
    else:
        saved = store.save_snapshot(snapshot, 'local-user')
        assert len(compact(saved.model_dump(mode='json'))) == LIMIT + offset
        assert store.get_snapshot(snapshot.id, 'local-user') == saved
        response = client.post('/api/snapshots/check', content=compact(saved.model_dump(mode='json')),
                               headers={'content-type': 'application/json'})
        assert response.status_code == 200
        assert response.json() == saved.model_dump(mode='json')
        assert len(response.content) == LIMIT + offset
        assert client.post('/api/snapshots/check', content=response.content,
                           headers={'content-type': 'application/json'}).status_code == 200
        assert response.json()['metadata'] == snapshot.metadata


@pytest.mark.parametrize('operation', ['check', 'save'])
def test_sparse_wire_expansion_rejected_before_acknowledgement(exchange, operation):
    store, client = exchange
    assert client.put('/api/snapshots', json=fixture()).status_code == 200
    before = db_state(store)
    payload = compact(at_bytes(LIMIT, canonical=False))
    response = client.request('POST' if operation == 'check' else 'PUT',
                              '/api/snapshots/check' if operation == 'check' else '/api/snapshots',
                              content=payload, headers={'content-type': 'application/json'})
    assert response.status_code == 413
    assert '16 MiB' in response.json()['detail']
    assert len(response.content) < 1024
    assert db_state(store) == before


@pytest.mark.parametrize('value', [float('nan'), float('inf'), '\ud800', b'bytes', {1: 'key'},
                                  {'tuple': (1, 2)}, {'set': {1}}, date(2026, 1, 1)])
def test_native_nonportable_metadata_only_rejected_at_wire_boundary(tmp_path, value):
    # Constructor remains usable by native CSV/XLSX label fallback consumers.
    data = fixture()
    data['metadata']['optional'] = value
    snapshot = Snapshot.model_validate(data)
    store = Store(tmp_path / 'state.sqlite')
    before = db_state(store)
    with pytest.raises(ValueError):
        store.save_snapshot(snapshot, 'local-user')
    assert db_state(store) == before


@pytest.mark.parametrize('shape', ['sparse', 'raw-overflow', 'schema', 'wire'])
def test_submit_validates_exact_retained_row_inside_transaction(exchange, shape):
    store, client = exchange
    saved = store.save_snapshot(Snapshot.model_validate(fixture()), 'local-user')
    data = {'sparse': lambda: sparse(4), 'raw-overflow': lambda: padded(50001),
            'schema': lambda: {'id': saved.id}, 'wire': lambda: at_bytes(LIMIT, canonical=False)}[shape]()
    with store.transaction() as conn:
        conn.execute('UPDATE snapshots SET payload=? WHERE id=?', (compact(data).decode(), saved.id))
    before = db_state(store)
    response = client.post('/api/jobs', json={'snapshot_id': saved.id, 'snapshot_revision': saved.revision})
    assert response.status_code in (413, 422)
    assert len(response.content) < 4096
    assert db_state(store) == before


@pytest.mark.parametrize('operation', ['copy', 'archive', 'restore'])
def test_old_sparse_row_cannot_be_rewritten(exchange, operation):
    store, client = exchange
    saved = store.save_snapshot(Snapshot.model_validate(fixture()), 'local-user')
    with store.transaction() as conn:
        conn.execute('UPDATE snapshots SET payload=?,archived=? WHERE id=?',
                     (compact(padded(50000, False)).decode(), operation == 'restore', saved.id))
    before = db_state(store)
    response = client.post('/api/snapshots/' + saved.id + '/' + operation, json={'revision': saved.revision})
    assert response.status_code == 422
    assert db_state(store) == before


@pytest.mark.parametrize('operation', ['save', 'copy', 'archive', 'restore'])
@pytest.mark.parametrize('fault', ['schema', 'units', 'serialization'])
def test_final_serialized_payload_failure_rolls_back_all_state(exchange, monkeypatch, operation, fault):
    import sp5generator.jobs as jobs
    store, client = exchange
    saved = store.save_snapshot(Snapshot.model_validate(fixture()), 'local-user')
    if operation == 'restore':
        saved = store.set_archived(saved.id, 'local-user', saved.revision, True)
    before = db_state(store)
    real_dump = Snapshot.model_dump
    real_json = Snapshot.model_dump_json

    def damage(data):
        if fault == 'serialization':
            raise ValueError('PRIVATE_SERIALIZER_VALUE' * 1000)
        if fault == 'schema':
            data['employees'][0]['target_minutes'] = -1
        else:
            data['software_versions'] = {f'v{i}': '1' for i in range(50001)}
        return data

    def dump(self, **kwargs):
        data = real_dump(self, **kwargs)
        return damage(data) if kwargs.get('mode') == 'json' else data

    def dump_json(self, **kwargs):
        return compact(damage(json.loads(real_json(self, **kwargs)))).decode()

    def no_summary(*args, **kwargs):
        raise AssertionError('Unvalidated final payload reached summary/SQL')

    monkeypatch.setattr(Snapshot, 'model_dump', dump)
    monkeypatch.setattr(Snapshot, 'model_dump_json', dump_json)
    monkeypatch.setattr(jobs, '_project_summary', no_summary)
    response = (client.put('/api/snapshots', json=fixture()) if operation == 'save'
                else client.post('/api/snapshots/' + saved.id + '/' + operation, json={'revision': saved.revision}))
    assert response.status_code == 422
    assert len(response.content) < 4096
    assert 'PRIVATE_SERIALIZER_VALUE' not in response.text
    assert db_state(store) == before


def test_model_copy_normalization_persists_and_returns_same_canonical_value(exchange):
    store, _ = exchange
    snapshot = Snapshot.model_validate(fixture())
    snapshot.employees[0] = snapshot.employees[0].model_copy(update={'target_minutes': '60'})
    saved = store.save_snapshot(snapshot, 'local-user')
    assert saved.employees[0].target_minutes == 60
    row = db_state(store)['snapshots'][0]
    assert json.loads(row['payload']) == saved.model_dump(mode='json')
    assert store.get_snapshot(saved.id, 'local-user') == saved


def test_history_appended_to_default_list_is_not_lost(exchange):
    from sp5generator.history_approvals import apply_history_approvals
    store, _ = exchange
    data = fixture()
    del data['employees'][0]['approvals']
    data['metadata']['history_matrix'] = [{'employee_id': 'p', 'suggested_approvals': [
        {'function_id': 'role', 'evidence_days': 3}]}]
    snapshot = Snapshot.model_validate(data)
    apply_history_approvals(snapshot)
    saved = store.save_snapshot(snapshot, 'local-user')
    assert len(store.get_snapshot(saved.id, 'local-user').employees[0].approvals) == 1


def test_metadata_and_identifiers_not_repaired_or_pruned(exchange):
    store, _ = exchange
    data = fixture()
    literal_id = ' ' + '𐐀' * 198 + ' '
    data['employees'][0]['id'] = literal_id
    data['metadata'] = {'unknown': [{'x': None}] * 50001, 'escape': '\n\r\t"\\',
                        'future': {'null': None, 'number': 1.25, 'bool': True, 'unicode': 'ä𐐀'}}
    original = deepcopy(data['metadata'])
    saved = store.save_snapshot(Snapshot.model_validate(data), 'local-user')
    assert saved.metadata == original
    assert saved.employees[0].id == literal_id
    assert store.get_snapshot(saved.id, 'local-user') == saved


@pytest.mark.parametrize('shape', ['deep', 'cycle'])
def test_native_nonportable_metadata_rejected_before_recursive_copy(exchange, shape):
    store, _ = exchange
    snapshot = store.save_snapshot(Snapshot.model_validate(fixture()), 'local-user')
    value = []
    if shape == 'deep':
        for _ in range(2000):
            value = [value]
    else:
        value.append(value)
    snapshot.metadata['optional'] = value
    before = db_state(store)
    with pytest.raises(ValueError, match=r'wire_format'):
        store.save_snapshot(snapshot, 'local-user')
    assert db_state(store) == before


def test_archive_sql_failure_after_snapshot_write_rolls_back_every_column(exchange):
    import sqlite3
    store, _ = exchange
    saved = store.save_snapshot(Snapshot.model_validate(fixture()), 'local-user')
    job = store.submit(saved.id, 'local-user', 1)
    store.cancel(job['id'], 'local-user')
    with store.transaction() as conn:
        conn.execute('INSERT INTO accepted VALUES(?,?,?)', (saved.id, 1, '{}'))
        conn.execute('INSERT INTO receipts VALUES(?,?,?,?)', ('synthetic-key', 'local-user', job['id'], '{}'))
        conn.execute('INSERT INTO audit(actor,job_id,created_at,payload) VALUES(?,?,?,?)',
                     ('local-user', job['id'], 1, '{}'))
        conn.execute("CREATE TRIGGER abort_archive BEFORE UPDATE OF archived ON snapshots "
                     "BEGIN SELECT RAISE(ABORT,'synthetic late failure'); END")
    before = db_state(store)
    assert all(before[table] for table in before)
    with pytest.raises(sqlite3.IntegrityError, match='synthetic late failure'):
        store.set_archived(saved.id, 'local-user', saved.revision, True)
    assert db_state(store) == before


def test_submit_keeps_selected_legacy_payload_and_validates_under_lock(exchange, monkeypatch):
    import sqlite3
    import sp5generator.jobs as jobs
    store, _ = exchange
    saved = store.save_snapshot(Snapshot.model_validate(fixture()), 'local-user')
    legacy = json.dumps(fixture(), ensure_ascii=True, indent=2)
    with store.transaction() as conn:
        conn.execute('UPDATE snapshots SET payload=? WHERE id=?', (legacy, saved.id))
    old_rows = db_state(store)['snapshots']
    real_prepare = jobs.prepare_snapshot_json
    seen = []

    def observe(snapshot):
        probe = sqlite3.connect(store.path, timeout=0)
        try:
            with pytest.raises(sqlite3.OperationalError, match='locked'):
                probe.execute('BEGIN IMMEDIATE')
        finally:
            probe.close()
        seen.append(snapshot)
        return real_prepare(snapshot)

    monkeypatch.setattr(jobs, 'prepare_snapshot_json', observe)
    job = store.submit(saved.id, 'local-user', 1, revision=saved.revision)
    assert len(seen) == 1 and seen[0] == Snapshot.model_validate_json(legacy)
    after = db_state(store)
    assert after['snapshots'] == old_rows
    assert after['jobs'][0]['id'] == job['id']
    assert after['jobs'][0]['payload'] == legacy


@pytest.mark.parametrize('operation', ['save', 'copy', 'archive', 'restore'])
def test_last_revision_or_copy_growth_rejected_before_write(exchange, operation):
    store, _ = exchange
    snapshot = Snapshot.model_validate(at_bytes(LIMIT))
    saved = store.save_snapshot(snapshot, 'local-user')
    data = saved.model_dump(mode='json')
    data['revision'] = '9'
    with store.transaction() as conn:
        conn.execute('UPDATE snapshots SET payload=?,revision=9,archived=? WHERE id=?',
                     (compact(data).decode(), operation == 'restore', saved.id))
    before = db_state(store)
    with pytest.raises(ValueError, match=r'wire_size_limit'):
        if operation == 'save':
            store.save_snapshot(Snapshot.model_validate(data), 'local-user')
        elif operation == 'copy':
            store.copy_snapshot(saved.id, 'local-user', '9')
        else:
            store.set_archived(saved.id, 'local-user', '9', operation == 'archive')
    assert db_state(store) == before


def test_escaped_input_normalizes_to_compact_utf8_without_data_loss(exchange):
    _, client = exchange
    data = fixture()
    data['employees'][0]['id'] = ' ' + '𐐀' * 198 + ' '
    data['metadata'] = {'unicode': 'ä𐐀💡', 'escaped': '\\n\\t\n\t"\\'}
    raw = json.dumps(data, ensure_ascii=True, separators=(',', ':')).encode()
    assert b'\\u' in raw
    response = client.post('/api/snapshots/check', content=raw, headers={'content-type': 'application/json'})
    assert response.status_code == 200
    assert response.json()['metadata'] == data['metadata']
    assert response.json()['employees'][0]['id'] == data['employees'][0]['id']
    assert response.content == compact(response.json())


def test_core_admission_has_no_web_extra_dependency(tmp_path):
    import subprocess
    import sys
    code = '''
import importlib.abc, sys
class NoWeb(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname.split('.')[0] in ('starlette', 'fastapi'):
            raise AssertionError('Core imported a web-only dependency')
sys.meta_path.insert(0, NoWeb())
from sp5generator.models import Snapshot, prepare_snapshot_json
from sp5generator.security_limits import bounded_canonical_json
assert bounded_canonical_json({'x': 'ä'}) == '{"x":"ä"}'
print('core-admission-import-ok')
'''
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=15)
    (tmp_path / 'core-import.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'core-admission-import-ok'
