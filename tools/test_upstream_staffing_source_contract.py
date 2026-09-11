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
