"""Retained-source copy admission: real HTTP/Store and exact SQLite state.

Only synthetic rows simulate legacy writers. JSON byte/state oracles are
independent of the product guard; metadata is not a planning-unit budget.
"""
from contextlib import contextmanager
import hashlib
import json
import sqlite3
import sys

import pytest

import sp5generator.jobs as jobs
from sp5generator.models import Snapshot
from sp5generator.security_limits import SnapshotWireError, SnapshotWireSizeExceeded
from test_review_budget_roundtrip import db_state, fixture, units
from test_review_budget_roundtrip import exchange as exchange

LIMIT = 16 * 1024 * 1024
OWNER = 'local-user'
PRIVATE = 'PRIVATE-SYNTHETIC-COPY'


def compact(data):
    return json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')


def state_digest(state):
    return hashlib.sha256(compact(state)).hexdigest()


def observe(**value):
    print('COPY-ADMISSION ' + json.dumps(value, sort_keys=True))


def seed_populated(store, *, source_id='s' * 200):
    data = fixture()
    data['id'] = source_id
    data['metadata'] = {
        'project_name': 'Synthetic source', 'accepted_revision': 7,
        'opaque': {'sentinel': PRIVATE, 'unicode': 'ä💡𐐀', 'escaped': '\0\n\t"\\',
                   'values': [None, True, -0.0, 10**40]}, 'pad': '',
    }
    saved = store.save_snapshot(Snapshot.model_validate(data), OWNER)
    job = store.submit(saved.id, OWNER, 1, revision=saved.revision)
    store.cancel(job['id'], OWNER)
    with store.transaction() as conn:
        conn.execute('INSERT INTO accepted VALUES(?,?,?)', (saved.id, 7, '{"synthetic":true}'))
        conn.execute('INSERT INTO receipts VALUES(?,?,?,?)',
                     ('synthetic-copy-receipt', OWNER, job['id'], '{"revision":7}'))
        conn.execute('INSERT INTO audit(actor,job_id,created_at,payload) VALUES(?,?,?,?)',
                     (OWNER, job['id'], 1, '{"synthetic":"copy"}'))
    assert all(db_state(store).values())
    return saved


def at_bytes(snapshot, target, *, key='pad'):
    data = snapshot.model_dump(mode='json')
    data['metadata'][key] = ''
    room = target - len(compact(data))
    assert room > 0
    data['metadata'][key] = 'x' * room
    assert len(compact(data)) == target
    assert units(data) < 50000
    return data


def retain(store, source_id, raw):
    with store.transaction() as conn:
        conn.execute('UPDATE snapshots SET payload=? WHERE id=?', (raw, source_id))


def assert_no_echo(text):
    assert len(text.encode('utf-8')) < 1024
    assert PRIVATE not in text
    assert 'x' * 64 not in text


@pytest.mark.parametrize('interface', ['http', 'store'])
@pytest.mark.parametrize('damage', ['ordinary-plus-one', 'removed-size', 'removed-nan'])
def test_invalid_retained_source_rejected_before_copy(exchange, interface, damage):
    store, client = exchange
    saved = seed_populated(store)
    if damage == 'removed-nan':
        data = saved.model_dump(mode='json')
        data['metadata']['accepted_revision'] = float('nan')
        raw = json.dumps(data, ensure_ascii=False, allow_nan=True, separators=(',', ':'))
        expected_status, expected_error = 422, SnapshotWireError
    else:
        data = at_bytes(saved, LIMIT + 1,
                        key='accepted_revision' if damage == 'removed-size' else 'pad')
        raw = compact(data).decode()
        expected_status, expected_error = 413, SnapshotWireSizeExceeded
    retain(store, saved.id, raw)
    before = db_state(store)
    assert all(before.values())
    # Existing consumers already reject these exact retained bytes.
    for response in (client.get('/api/snapshots/' + saved.id),
                     client.post('/api/jobs', json={'snapshot_id': saved.id,
                                                   'snapshot_revision': saved.revision})):
        assert response.status_code == expected_status
        assert_no_echo(response.text)
        assert db_state(store) == before
    error = None
    copied = None
    if interface == 'http':
        response = client.post('/api/snapshots/' + saved.id + '/copy',
                               json={'revision': saved.revision})
        status = response.status_code
        output_bytes = len(response.content)
    else:
        try:
            copied = store.copy_snapshot(saved.id, OWNER, saved.revision)
        except ValueError as exc:
            error = exc
        status = (413 if isinstance(error, SnapshotWireSizeExceeded) else 422) if error else 200
        output_bytes = len(str(error).encode()) if error else len(compact(copied.model_dump(mode='json')))
    after = db_state(store)
    observe(case='retained-rejection', damage=damage, interface=interface,
            retained_bytes=len(raw.encode()), source_units=units(data), source_id_length=len(saved.id),
            expected_status=expected_status, status=status, output_bytes=output_bytes,
            before_sha256=state_digest(before), after_sha256=state_digest(after),
            rows_before={table: len(rows) for table, rows in before.items()},
            rows_after={table: len(rows) for table, rows in after.items()})
    assert status == expected_status, 'Copy must admit the retained source before shortening IDs or removing metadata'
    if interface == 'http':
        assert_no_echo(response.text)
    else:
        assert type(error) is expected_error
        assert copied is None
        assert_no_echo(str(error))
    assert after == before


@pytest.mark.parametrize('interface', ['http', 'store'])
@pytest.mark.parametrize('key', ['pad', 'accepted_revision'])
@pytest.mark.parametrize('offset', [-1, 0])
def test_admissible_long_id_source_at_wire_boundary_copies(exchange, interface, key, offset):
    store, client = exchange
    saved = seed_populated(store)
    data = at_bytes(saved, LIMIT + offset, key=key)
    raw = compact(data)
    retain(store, saved.id, raw.decode())
    before = db_state(store)
    assert len(saved.id) == 200
    assert client.get('/api/snapshots/' + saved.id).content == raw
    if interface == 'http':
        response = client.post('/api/snapshots/' + saved.id + '/copy', json={'revision': saved.revision})
        assert response.status_code == 200
        copied = response.json()
    else:
        copied = store.copy_snapshot(saved.id, OWNER, saved.revision).model_dump(mode='json')
    assert copied['id'] != saved.id and copied['revision'] == '1'
    assert copied['created_at'] != data['created_at']
    assert copied['metadata']['opaque'] == data['metadata']['opaque']
    assert copied['metadata']['pad'] == data['metadata']['pad']
    assert copied['metadata']['project_name'] == 'Synthetic source – Kopie'
    assert 'accepted_revision' not in copied['metadata']
    assert len(compact(copied)) <= LIMIT
    assert client.get('/api/snapshots/' + copied['id']).content == compact(copied)
    assert client.post('/api/snapshots/check', content=compact(copied),
                       headers={'content-type': 'application/json'}).content == compact(copied)
    after = db_state(store)
    assert after['snapshots'][:-1] == before['snapshots']
    assert after['snapshots'][-1]['id'] == copied['id']
    assert after['snapshots'][-1]['payload'].encode() == compact(copied)
    assert {k: v for k, v in after.items() if k != 'snapshots'} == {
        k: v for k, v in before.items() if k != 'snapshots'}
    observe(case='admissible-boundary', interface=interface, key=key, offset=offset,
            source_id_length=len(saved.id), source_bytes=len(raw), copy_bytes=len(compact(copied)),
            original_row_unchanged=True, auxiliary_tables_unchanged=True, copy_replays=True)


@pytest.mark.parametrize('leading_whitespace', [0, LIMIT + 1])
def test_sparse_whitespace_retained_source_is_not_rewritten_or_raw_capped(exchange, leading_whitespace):
    store, client = exchange
    saved = seed_populated(store)
    data = fixture()  # Omitted defaults must remain omitted in the retained row.
    data.update(id=saved.id, revision='7', metadata=saved.model_dump(mode='json')['metadata'])
    raw = ' ' * leading_whitespace + json.dumps(data, ensure_ascii=True, indent=3)
    with store.transaction() as conn:
        conn.execute('UPDATE snapshots SET payload=?,revision=7 WHERE id=?', (raw, saved.id))
    before = db_state(store)
    canonical = Snapshot.model_validate_json(raw).model_dump(mode='json')
    assert len(compact(canonical)) < LIMIT
    if leading_whitespace:
        assert len(raw.encode()) > LIMIT
    response = client.post('/api/snapshots/' + saved.id + '/copy',
                           json={'revision': '7', 'project_name': 'Explicit synthetic copy'})
    assert response.status_code == 200
    copied = response.json()
    expected = dict(canonical, id=copied['id'], revision='1', created_at=copied['created_at'])
    expected['metadata'] = {**canonical['metadata'], 'project_name': 'Explicit synthetic copy'}
    del expected['metadata']['accepted_revision']
    assert copied == expected
    assert client.get('/api/snapshots/' + saved.id).json() == canonical
    assert client.get('/api/snapshots/' + copied['id']).json() == copied
    after = db_state(store)
    assert after['snapshots'][:-1] == before['snapshots']
    assert after['snapshots'][0]['payload'] == raw
    assert after['snapshots'][0]['revision'] == 7
    assert {k: v for k, v in after.items() if k != 'snapshots'} == {
        k: v for k, v in before.items() if k != 'snapshots'}
    observe(case='legacy-sparse-whitespace', stored_text_bytes=len(raw.encode()),
            canonical_bytes=len(compact(canonical)), original_row_unchanged=True,
            auxiliary_tables_unchanged=True, accepted_revision_removed=True)


@pytest.mark.parametrize('interface', ['http', 'store'])
@pytest.mark.parametrize('reason', ['other-owner', 'stale-revision'])
def test_owner_and_revision_precede_invalid_source_admission(exchange, interface, reason):
    store, client = exchange
    saved = seed_populated(store)
    data = saved.model_dump(mode='json')
    data['metadata']['accepted_revision'] = float('nan')
    retain(store, saved.id, json.dumps(data, allow_nan=True))
    if reason == 'other-owner':
        with store.transaction() as conn:
            conn.execute('UPDATE snapshots SET owner=? WHERE id=?', ('another-owner', saved.id))
    revision = 'stale' if reason == 'stale-revision' else saved.revision
    before = db_state(store)
    expected_status = 404 if reason == 'other-owner' else 409
    if interface == 'http':
        response = client.post('/api/snapshots/' + saved.id + '/copy', json={'revision': revision})
        assert response.status_code == expected_status
        assert_no_echo(response.text)
    else:
        with pytest.raises(KeyError if reason == 'other-owner' else jobs.Conflict):
            store.copy_snapshot(saved.id, OWNER, revision)
    assert db_state(store) == before
    observe(case='authorization-revision-first', reason=reason, interface=interface,
            status=expected_status, all_five_tables_unchanged=True)


@contextmanager
def measured_preparations(store):
    """Observe unchanged functions; never replace a product guard/serializer.

    A second real SQLite writer attempts BEGIN IMMEDIATE at each preparation.
    Profiling also captures the exact selected row and product connection count.
    """
    observed = {'values': [], 'selected_payloads': [], 'connections': 0}
    previous = sys.getprofile()

    def profile(frame, event, arg):
        if event == 'c_call' and arg is sqlite3.connect:
            observed['connections'] += 1
        if event == 'return' and frame.f_code is jobs.Store._project_for_update.__code__:
            observed['selected_payloads'].append(arg['payload'])
        if event == 'call' and frame.f_code is jobs.prepare_snapshot_json.__code__:
            probe = sqlite3.connect(store.path, timeout=0, isolation_level=None)
            try:
                with pytest.raises(sqlite3.OperationalError, match='locked'):
                    probe.execute('BEGIN IMMEDIATE')
            finally:
                probe.close()
            observed['values'].append(frame.f_locals['snapshot'].model_dump(mode='json'))

    sys.setprofile(profile)
    try:
        yield observed
    finally:
        sys.setprofile(previous)


@pytest.mark.parametrize('oversized', [False, True])
def test_exact_selected_source_prepared_unmutated_under_copy_lock(exchange, oversized):
    store, _ = exchange
    saved = seed_populated(store)
    data = at_bytes(saved, LIMIT + 1) if oversized else saved.model_dump(mode='json')
    data['revision'] = '7'
    raw = compact(data).decode()
    with store.transaction() as conn:
        conn.execute('UPDATE snapshots SET payload=?,revision=7 WHERE id=?', (raw, saved.id))
    before = db_state(store)
    with measured_preparations(store) as observed:
        if oversized:
            with pytest.raises(SnapshotWireSizeExceeded):
                store.copy_snapshot(saved.id, OWNER, '7')
        else:
            copied = store.copy_snapshot(saved.id, OWNER, '7', 'Explicit synthetic copy')
    assert observed['connections'] == 1, 'Copy must not reopen or reread through another connection'
    assert observed['selected_payloads'] == [raw]
    assert observed['values'][0] == data, 'Source ID/revision/time/name/acceptance metadata changed before admission'
    assert len(observed['values']) == (1 if oversized else 2)
    after = db_state(store)
    if oversized:
        assert after == before
    else:
        assert observed['values'][1] == copied.model_dump(mode='json')
        assert after['snapshots'][:-1] == before['snapshots']
        assert {k: v for k, v in after.items() if k != 'snapshots'} == {
            k: v for k, v in before.items() if k != 'snapshots'}
    observe(case='selected-source-under-lock', oversized=oversized,
            retained_sha256=hashlib.sha256(raw.encode()).hexdigest(),
            source_prepared_before_mutation=True, locked_at_each_preparation=True,
            preparations=len(observed['values']), product_connections=observed['connections'])


@pytest.mark.parametrize('interface', ['http', 'store'])
def test_source_eligibility_does_not_bypass_final_copy_growth_guard(exchange, interface):
    store, client = exchange
    saved = seed_populated(store, source_id='s')
    raw = compact(at_bytes(saved, LIMIT))
    retain(store, saved.id, raw.decode())
    assert client.get('/api/snapshots/' + saved.id).content == raw
    before = db_state(store)
    if interface == 'http':
        response = client.post('/api/snapshots/' + saved.id + '/copy',
                               json={'revision': saved.revision, 'project_name': 'N' * 120})
        assert response.status_code == 413
        assert_no_echo(response.text)
    else:
        with measured_preparations(store) as observed:
            with pytest.raises(SnapshotWireSizeExceeded) as error:
                store.copy_snapshot(saved.id, OWNER, saved.revision, 'N' * 120)
        assert_no_echo(str(error.value))
        assert len(observed['values']) == 2
        assert len(compact(observed['values'][0])) == LIMIT
        assert len(compact(observed['values'][1])) > LIMIT
    after = db_state(store)
    assert after == before
    observe(case='final-output-growth', interface=interface, source_bytes=len(raw),
            before_sha256=state_digest(before), after_sha256=state_digest(after), status=413)
