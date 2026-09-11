"""Synthetic DBF -> real Library mapping -> isolated API GET contract.

SP5_STAFFING_ROUTER selects the patched master_data.py; SP5_STRICT_READER
selects the patched reader. No production API, authentication or data accessed.
"""
import ast
import importlib.util
import os
import json
import subprocess
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit

import pytest
from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.testclient import TestClient
from sp5lib.database import SP5Database
from sp5generator.api_adapter import APIClient, APIImportError

from test_upstream_source_read_integrity import synthetic_dbf
from tools.selected_work_segments_candidate import StrictSourceTables


@pytest.fixture
def source(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('strict_reader', os.environ['SP5_STRICT_READER'])
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    db = SP5Database(str(tmp_path))
    monkeypatch.setattr(db, 'get_shifts', lambda **kwargs: [])
    monkeypatch.setattr(db, 'get_workplaces', lambda **kwargs: [])
    for table in ('SHDEM', 'DADEM', 'SPDEM'):
        (tmp_path / f'5{table}.DBF').write_bytes(synthetic_dbf([]))
    strict = StrictSourceTables(db, reader.read_dbf)
    monkeypatch.setattr(db, '_read', strict._read)
    return db, reader, tmp_path


@pytest.fixture
def client(source):
    db, reader, _ = source
    path = Path(os.environ['SP5_STAFFING_ROUTER'])
    names = {'_staffing_source_error', 'get_staffing_requirements', 'get_special_staffing'}
    nodes = [n for n in ast.parse(path.read_text()).body
             if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(nodes) == 3
    sanitized = []

    def sanitize(error):
        sanitized.append(error)
        return HTTPException(500, 'Internal server error')

    namespace = {'router': APIRouter(), 'Query': Query, 'HTTPException': HTTPException,
                 'get_db': lambda: db, '_sanitize_500': sanitize,
                 **{name: getattr(reader, name) for name in
                    ('DBFReadError', 'DBFStructureError', 'DBFValueError')}}
    # Keep actual decorators, paths, Query defaults and filtering functions.
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    app = FastAPI()
    app.include_router(namespace['router'])
    with TestClient(app, raise_server_exceptions=False) as http:
        yield http, sanitized


ROUTES = [('SHDEM', '/api/staffing-requirements', 'get_staffing_requirements'),
          ('SPDEM', '/api/staffing-requirements/special', 'get_special_staffing')]


@pytest.mark.parametrize('table,url,method', ROUTES)
@pytest.mark.parametrize('field', ['MIN', 'MAX'])
@pytest.mark.parametrize('raw,category', [(b'0000', None), (b'    ', 'numeric_value'),
                                       (b'nope', 'numeric_value'), (b' NaN', 'numeric_value')])
def test_numeric_source_to_http(source, client, table, url, method, field, raw, category):
    _, _, path = source
    payload = bytearray(synthetic_dbf([b' ' + raw]))
    payload[32:43] = field.encode().ljust(11, b'\0')
    payload[49] = 1  # Accept floats in legacy parser, including NaN.
    (path / f'5{table}.DBF').write_bytes(payload)
    http, sanitized = client
    response = http.get(url)
    if category:
        assert response.status_code == 500
        assert_source_error(response, category)
        assert sanitized == []
    else:
        assert response.status_code == 200
        rows = response.json()['shift_requirements'] if table == 'SHDEM' else response.json()
        assert rows[0][field.lower()] == 0


@pytest.mark.parametrize('table,url,method', ROUTES)
@pytest.mark.parametrize('failure,category', [('missing', 'read'), ('truncated', 'structure')])
def test_read_and_structure_failure_no_empty_success(source, client, table, url, method,
                                                    failure, category):
    _, _, path = source
    file = path / f'5{table}.DBF'
    if failure == 'missing':
        file.unlink()
    else:
        file.write_bytes(synthetic_dbf([b' 0000'], declared=2))
    http, sanitized = client
    response = http.get(url)
    assert response.status_code == 500
    assert_source_error(response, category)
    assert sanitized == []


@pytest.mark.parametrize('table,url,method', ROUTES)
@pytest.mark.parametrize('field_index', [0, 1])
@pytest.mark.parametrize('raw', [b'0000', b'    ', b'nope'])
def test_required_count_column_wrong_type_is_not_yet_rejected(
        source, client, monkeypatch, table, url, method, field_index, raw):
    """Characterize the remaining schema gap; presence is not a numeric contract."""
    db, reader, path = source
    values = [b'0000', b'0000']
    values[field_index] = raw
    payload = bytearray(staffing_columns(('MIN', 'MAX'), [b' ' + b''.join(values)]))
    payload[32 + 32 * field_index + 11] = ord('C')
    (path / f'5{table}.DBF').write_bytes(payload)
    original_read = db._read

    def read(name):
        if name == table:
            return reader.read_dbf(db._table(name), strict=True,
                                   required_fields=('MIN', 'MAX'))
        return original_read(name)

    monkeypatch.setattr(db, '_read', read)
    http, sanitized = client
    response = http.get(url)
    assert response.status_code == 200
    rows = response.json()['shift_requirements'] if table == 'SHDEM' else response.json()
    value = rows[0][('min', 'max')[field_index]]
    assert isinstance(value, str)
    assert value == raw.decode().strip()
    assert sanitized == []


@pytest.mark.parametrize('table,url,method', ROUTES)
@pytest.mark.parametrize('kind', ['DBFReadError', 'DBFStructureError', 'DBFValueError', 'unknown'])
def test_exception_contents_never_in_response(source, client, monkeypatch, table, url, method, kind):
    db, reader, _ = source
    error_type = RuntimeError if kind == 'unknown' else getattr(reader, kind)
    error = error_type('SYNTHETIC_PRIVATE_PATH_AND_VALUE')

    def fail(**kwargs):
        raise error

    monkeypatch.setattr(db, method, fail)
    http, sanitized = client
    response = http.get(url)
    assert response.status_code == 500
    assert 'SYNTHETIC_PRIVATE' not in response.text
    assert sanitized == ([error] if kind == 'unknown' else [])


@pytest.mark.parametrize('table,url,method', ROUTES)
def test_valid_empty_sources_remain_valid(source, client, table, url, method):
    http, _ = client
    response = http.get(url)
    assert response.status_code == 200
    rows = response.json()['shift_requirements'] if table == 'SHDEM' else response.json()
    assert rows == []


def test_existing_group_filter_and_query_forwarding(source, client, monkeypatch):
    db, _, _ = source
    calls = []

    def regular(**kwargs):
        calls.append(kwargs)
        return {'shift_requirements': [{'group_id': group} for group in (None, 1, 2)],
                'daily_requirements': []}

    def special(**kwargs):
        calls.append(kwargs)
        return []

    monkeypatch.setattr(db, 'get_staffing_requirements', regular)
    monkeypatch.setattr(db, 'get_special_staffing', special)
    http, _ = client
    response = http.get('/api/staffing-requirements?year=2026&month=9&group_id=1')
    assert response.status_code == 200
    assert response.json()['shift_requirements'] == [{'group_id': None}, {'group_id': 1}]
    assert http.get('/api/staffing-requirements/special?date=2026-09-01&group_id=1').status_code == 200
    assert calls == [{'year': 2026, 'month': 9}, {'date': '2026-09-01', 'group_id': 1}]


@pytest.mark.parametrize('table,url,method', ROUTES)
def test_generator_aborts_and_does_not_cache_failed_source(source, client, table, url, method):
    _, _, path = source
    payload = bytearray(synthetic_dbf([b'     ']))
    payload[32:43] = b'MAX'.ljust(11, b'\0')
    file = path / f'5{table}.DBF'
    file.write_bytes(payload)
    http, _ = client

    class ASGITransport:
        def open(self, request, **kwargs):
            response = http.get(urlsplit(request.full_url).path)
            if response.status_code >= 400:
                raise HTTPError(request.full_url, response.status_code, 'source failure',
                                response.headers, BytesIO(response.content))
            return BytesIO(response.content)

    # Exercise the real reader/cache without a production login or socket.
    api = object.__new__(APIClient)
    api.base, api.headers, api.cache = 'http://synthetic.test', {}, {}
    api.opener = ASGITransport()
    with pytest.raises(APIImportError, match='ungeklärte Zahlenwerte.*HTTP 500'):
        api.get(url)
    assert api.cache == {}
    # A retry must actually reread; no empty successful cache entry was created.
    file.write_bytes(synthetic_dbf([]))
    result = api.get(url)
    assert (result['shift_requirements'] if table == 'SHDEM' else result) == []


MESSAGES = {
    'temporal_value': 'Bedarfsquelle enthält ungültige Datums- oder Wochentagswerte.',
    'numeric_value': 'Bedarfsquelle enthält ungeklärte Zahlenwerte.',
    'structure': 'Bedarfsquelle ist strukturell unvollständig oder ungültig.',
    'read': 'Bedarfsquelle konnte nicht vollständig gelesen werden.',
}


def assert_source_error(response, category):
    assert response.json() == {'detail': MESSAGES[category]}
    assert response.headers['x-sp5-error-code'] == 'staffing_source_unresolved'
    assert response.headers['x-sp5-error-category'] == category


@pytest.mark.parametrize('table,url,method', ROUTES)
@pytest.mark.parametrize('category,kind', [('numeric_value', 'DBFValueError'),
                                         ('structure', 'DBFStructureError'),
                                         ('read', 'DBFReadError')])
def test_existing_osp5_consumer_reads_actual_http_error(source, client, monkeypatch,
                                                       table, url, method, category, kind):
    db, reader, _ = source

    def fail(**kwargs):
        raise getattr(reader, kind)('SYNTHETIC_PRIVATE_PATH_AND_VALUE')

    monkeypatch.setattr(db, method, fail)
    http, _ = client
    response = http.get(url)
    assert_source_error(response, category)
    completed = subprocess.run(
        ['node', 'tools/audit_upstream_staffing_error.cjs', os.environ['SP5_OSP5_FRONTEND']],
        input=json.dumps(response.json()), text=True, capture_output=True, check=True,
    )
    assert json.loads(completed.stdout) == MESSAGES[category]


@pytest.mark.parametrize('table,url,method', ROUTES)
@pytest.mark.parametrize('missing', ['MIN', 'MAX'])
def test_missing_count_column_currently_becomes_zero(source, client, table, url, method, missing):
    """Characterize a remaining schema gap, not an approved default.

    Strict byte/numeric validation sees only columns present in the DBF.
    Library r.get(..., 0) still fabricates the absent counterpart as zero.
    """
    _, _, path = source
    present = 'MAX' if missing == 'MIN' else 'MIN'
    payload = bytearray(synthetic_dbf([b' 0001']))
    payload[32:43] = present.encode().ljust(11, b'\0')
    (path / f'5{table}.DBF').write_bytes(payload)
    http, sanitized = client
    response = http.get(url)
    assert response.status_code == 200
    rows = response.json()['shift_requirements'] if table == 'SHDEM' else response.json()
    assert rows[0][present.lower()] == 1
    assert rows[0][missing.lower()] == 0
    assert sanitized == []


def staffing_columns(fields, records=()):
    """Synthetic descriptors, including empty/deleted-only schema cases."""
    import struct
    header = bytearray(32)
    header[0] = 3
    struct.pack_into('<IHH', header, 4, len(records), 33 + 32 * len(fields),
                     1 + 4 * len(fields))
    descriptors = bytearray()
    for name in fields:
        field = bytearray(32)
        field[:11] = name.encode().ljust(11, b'\0')
        field[11] = ord('N')
        field[16] = 4
        descriptors.extend(field)
    return bytes(header + descriptors) + b'\r' + b''.join(records)


@pytest.mark.parametrize('table,url,method', ROUTES)
@pytest.mark.parametrize('require_temporal', [False, True])
def test_missing_staffing_temporal_descriptor(
        source, client, monkeypatch, table, url, method, require_temporal):
    """Missing DATE is hidden by date filtering, not by Generator's team-only GET."""
    db, reader, path = source
    fields = ('MIN', 'MAX', 'GROUPID', 'SHIFTID', 'WORKPLACID')
    temporal = 'DATE' if table == 'SPDEM' else 'WEEKDAY'
    (path / f'5{table}.DBF').write_bytes(
        staffing_columns(fields, [b' ' + b'0001' * len(fields)]))
    original_read = db._read

    def read(name):
        if name == table:
            return reader.read_dbf(
                db._table(name), strict=True, numeric_fields=('MIN', 'MAX'),
                required_fields=fields[2:] + ((temporal,) if require_temporal else ()))
        return original_read(name)

    monkeypatch.setattr(db, '_read', read)
    http, sanitized = client
    queries = ('', '?group_id=1', '?group_id=1&date=2026-09-01')
    responses = [http.get(url + query) for query in queries]
    if require_temporal:
        for response in responses:
            assert response.status_code == 500
            assert_source_error(response, 'structure')
    else:
        assert all(response.status_code == 200 for response in responses)
        rows = [(response.json()['shift_requirements'] if table == 'SHDEM'
                 else response.json()) for response in responses]
        assert len(rows[0]) == len(rows[1]) == 1
        assert rows[0] == rows[1]
        assert rows[0][0][temporal.lower()] == ('' if table == 'SPDEM' else None)
        assert rows[2] == ([] if table == 'SPDEM' else rows[0])
    assert sanitized == []


@pytest.mark.parametrize('table,url,method', ROUTES)
@pytest.mark.parametrize('require_identity', [False, True])
@pytest.mark.parametrize('missing,output', [('GROUPID', 'group_id'),
                                           ('SHIFTID', 'shift_id'),
                                           ('WORKPLACID', 'workplace_id')])
def test_missing_staffing_identity_survives_count_contract(
        source, client, monkeypatch, table, url, method, missing, output, require_identity):
    """Characterization: missing scope can disappear before Generator sees it.

    This is not permission to treat missing team identity as global staffing.
    Keep all present identity values valid; only remove one DBF descriptor.
    """
    db, reader, path = source
    fields = tuple(name for name in ('MIN', 'MAX', 'GROUPID', 'SHIFTID', 'WORKPLACID')
                   if name != missing)
    (path / f'5{table}.DBF').write_bytes(
        staffing_columns(fields, [b' ' + b'0001' * len(fields)]))
    original_read = db._read

    def read(name):
        if name == table:
            return reader.read_dbf(db._table(name), strict=True,
                                   numeric_fields=('MIN', 'MAX'),
                                   required_fields=(('GROUPID', 'SHIFTID', 'WORKPLACID')
                                                    if require_identity else ()))
        return original_read(name)

    monkeypatch.setattr(db, '_read', read)
    http, sanitized = client
    unfiltered = http.get(url)
    if require_identity:
        # Existing required_fields mechanism rejects the malformed source before
        # Library mapping/filtering; no interpretation of zero/global IDs needed.
        for response in (unfiltered, http.get(url + '?group_id=1')):
            assert response.status_code == 500
            assert_source_error(response, 'structure')
        assert sanitized == []
        return
    assert unfiltered.status_code == 200
    rows = (unfiltered.json()['shift_requirements'] if table == 'SHDEM'
            else unfiltered.json())
    assert len(rows) == 1 and rows[0][output] is None
    assert rows[0]['min'] == rows[0]['max'] == 1
    scoped = http.get(url + '?group_id=1')
    assert scoped.status_code == 200
    scoped_rows = (scoped.json()['shift_requirements'] if table == 'SHDEM'
                   else scoped.json())
    # Regular API preserves unknown scope; special Library filters it away.
    assert scoped_rows == ([] if table == 'SPDEM' and missing == 'GROUPID' else rows)
    assert sanitized == []


@pytest.mark.parametrize('table,url,method', ROUTES)
@pytest.mark.parametrize('fields', [('MIN',), ('MAX',), ('MIN', 'MAX', 'MAX'), ('MIN', 'MAX')])
@pytest.mark.parametrize('state', ['empty', 'deleted', 'zero'])
def test_explicit_staffing_column_contract(source, client, monkeypatch, table, url, method,
                                           fields, state):
    db, reader, path = source
    marker = b'*' if state == 'deleted' else b' '
    records = [] if state == 'empty' else [marker + b'0000' * len(fields)]
    (path / f'5{table}.DBF').write_bytes(staffing_columns(fields, records))
    original_read = db._read

    def read(name):
        if name == table:
            return reader.read_dbf(db._table(name), strict=True, required_fields=('MIN', 'MAX'))
        return original_read(name)

    monkeypatch.setattr(db, '_read', read)
    http, sanitized = client
    response = http.get(url)
    if fields != ('MIN', 'MAX'):
        assert response.status_code == 500
        assert_source_error(response, 'structure')
    else:
        assert response.status_code == 200
        rows = response.json()['shift_requirements'] if table == 'SHDEM' else response.json()
        if state == 'zero':
            assert rows[0]['min'] == rows[0]['max'] == 0
        else:
            assert rows == []
    assert sanitized == []


@pytest.mark.parametrize('table,url,method', ROUTES)
@pytest.mark.parametrize('field_index', [0, 1])
@pytest.mark.parametrize('field_type', ['C', 'L', 'D', 'N', 'F'])
@pytest.mark.parametrize('state', ['empty', 'deleted', 'zero', 'unlimited'])
def test_explicit_numeric_staffing_contract(source, client, monkeypatch, table, url, method,
                                            field_index, field_type, state):
    db, reader, path = source
    marker = b'*' if state == 'deleted' else b' '
    values = b'0000' + (b'  -1' if state == 'unlimited' else b'0000')
    records = [] if state == 'empty' else [marker + values]
    payload = bytearray(staffing_columns(('MIN', 'MAX'), records))
    payload[32 + 32 * field_index + 11] = ord(field_type)
    (path / f'5{table}.DBF').write_bytes(payload)
    original_read = db._read

    def read(name):
        if name == table:
            return reader.read_dbf(db._table(name), strict=True,
                                   numeric_fields=('MIN', 'MAX'))
        return original_read(name)

    monkeypatch.setattr(db, '_read', read)
    http, sanitized = client
    response = http.get(url)
    if field_type not in ('N', 'F'):
        assert response.status_code == 500
        assert_source_error(response, 'structure')
    else:
        assert response.status_code == 200
        rows = response.json()['shift_requirements'] if table == 'SHDEM' else response.json()
        if state in ('empty', 'deleted'):
            assert rows == []
        else:
            assert rows[0]['min'] == 0
            assert rows[0]['max'] == (-1 if state == 'unlimited' else 0)
    assert sanitized == []


@pytest.mark.parametrize('table,url,method', ROUTES)
@pytest.mark.parametrize('state', ['populated', 'empty', 'deleted'])
@pytest.mark.parametrize('kind', ['valid', 'blank', 'invalid', 'wrong_type'])
@pytest.mark.parametrize('calendar_opt_in', [False, True])
def test_temporal_presence_does_not_validate_value(
        source, client, monkeypatch, table, url, method, state, kind, calendar_opt_in):
    """Required descriptors alone cannot establish usable calendar semantics."""
    import struct

    db, reader, path = source
    temporal = 'DATE' if table == 'SPDEM' else 'WEEKDAY'
    cases = ({'valid': ('D', b'20260901', '2026-09-01'),
              'blank': ('D', b'        ', None),
              'invalid': ('D', b'20260230', None),
              'wrong_type': ('N', b'20260901', 20260901)} if table == 'SPDEM' else
             {'valid': ('N', b'0007', 7),  # Holiday slot is valid, not day 8.
              'blank': ('N', b'    ', 0),
              'invalid': ('N', b'0008', 8),
              'wrong_type': ('D', b'20260901', '2026-09-01')})
    ftype, raw, expected = cases[kind]
    fields = ('MIN', 'MAX', 'GROUPID', 'SHIFTID', 'WORKPLACID', temporal)
    payload = bytearray(staffing_columns(fields, []))
    payload[32 + 5 * 32 + 11] = ord(ftype)
    payload[32 + 5 * 32 + 16] = len(raw)
    records = [] if state == 'empty' else [
        (b'*' if state == 'deleted' else b' ') + b'0001' * 5 + raw]
    struct.pack_into('<I', payload, 4, len(records))
    struct.pack_into('<H', payload, 10, 1 + 20 + len(raw))
    (path / f'5{table}.DBF').write_bytes(bytes(payload) + b''.join(records))
    original_read = db._read

    def read(name):
        if name == table:
            return reader.read_dbf(db._table(name), strict=True,
                                   numeric_fields=('MIN', 'MAX'), required_fields=fields,
                                   **({('date_fields' if table == 'SPDEM' else 'weekday_fields'):
                                       (temporal,)} if calendar_opt_in else {}))
        return original_read(name)

    monkeypatch.setattr(db, '_read', read)
    http, sanitized = client
    response = http.get(url + '?group_id=1')
    if calendar_opt_in and (kind == 'wrong_type' or
                            (state == 'populated' and kind in ('blank', 'invalid'))):
        category = ('structure' if kind == 'wrong_type' else
                    'numeric_value' if table == 'SHDEM' and kind == 'blank' else
                    'temporal_value')
        assert response.status_code == 500
        assert_source_error(response, category)
        assert sanitized == []
        # Filtering must not hide corrupt source rows as a successful empty result.
        filtered = http.get(url + '?group_id=999&date=2026-09-01')
        assert filtered.status_code == 500
        assert_source_error(filtered, category)
        return
    if table == 'SHDEM' and kind == 'blank' and state == 'populated':
        assert response.status_code == 500
        assert_source_error(response, 'numeric_value')
        assert sanitized == []
        return
    assert response.status_code == 200
    rows = response.json()['shift_requirements'] if table == 'SHDEM' else response.json()
    if state != 'populated':
        assert rows == []
    else:
        assert len(rows) == 1
        assert rows[0][temporal.lower()] == expected
    if table == 'SPDEM':
        filtered = http.get(url + '?group_id=1&date=2026-09-01')
        assert filtered.status_code == 200
        assert filtered.json() == (rows if kind == 'valid' else [])
    assert sanitized == []


@pytest.mark.parametrize('table,url,method', ROUTES)
@pytest.mark.parametrize('args,category', [
    (('invalid_required_date',), 'temporal_value'),
    (('invalid_required_weekday',), 'temporal_value'),
    (('invalid_required_date SYNTHETIC_PRIVATE',), 'numeric_value'),
    (('invalid_required_date', 'SYNTHETIC_PRIVATE'), 'numeric_value'),
    ((), 'numeric_value'),
])
def test_temporal_error_allowlist_is_source_free(source, client, monkeypatch,
                                                table, url, method, args, category):
    db, reader, _ = source

    def fail(**kwargs):
        error = reader.DBFValueError('synthetic')
        error.args = args  # Exercise malformed exception metadata without constructor errors.
        raise error

    monkeypatch.setattr(db, method, fail)
    http, sanitized = client
    response = http.get(url, params={'group_id': 999})
    assert response.status_code == 500
    assert_source_error(response, category)
    assert 'SYNTHETIC_PRIVATE' not in response.text
    assert sanitized == []
    completed = subprocess.run(
        ['node', 'tools/audit_upstream_staffing_error.cjs', os.environ['SP5_OSP5_FRONTEND']],
        input=json.dumps(response.json()), text=True, capture_output=True, check=True,
    )
    assert json.loads(completed.stdout) == MESSAGES[category]
