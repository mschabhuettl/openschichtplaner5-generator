"""Opt-in ID contract rebuilt from clean tracked source; synthetic bytes only."""
import importlib.util
import os
from pathlib import Path
import subprocess
import struct

import pytest

from tools.test_upstream_staffing_source_contract import staffing_columns


@pytest.fixture(scope='module')
def reader(tmp_path_factory):
    root = tmp_path_factory.mktemp('identity-reader')
    path = root / 'sp5lib/dbf_reader.py'
    path.parent.mkdir()
    source = os.environ['SP5_LIBRARY_SOURCE']
    path.write_bytes(subprocess.check_output(
        ['git', '-C', source, 'show', 'HEAD:sp5lib/dbf_reader.py']))
    for name in ('strict', 'temporal', 'identity'):
        patch = Path(__file__).with_name(f'upstream-library-{name}-reader-candidate.patch')
        subprocess.run(['git', 'apply', str(patch.resolve())], cwd=root, check=True,
                       capture_output=True)
    spec = importlib.util.spec_from_file_location('identity_reader_candidate', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('name', ['GROUPID', 'SHIFTID', 'WORKPLACID'])
@pytest.mark.parametrize('ftype,raw,expected', [
    ('N', b'0001', 1), ('N', b' 1.0', 1), ('F', b' 1.0', 1),
    ('N', b'0000', 0), ('N', b'  -1', -1),
    ('N', b' 1.5', None), ('N', b'    ', None), ('N', b'nope', None),
    ('L', b'   T', None), ('M', b'0001', None),
])
@pytest.mark.parametrize('state', ['active', 'deleted', 'empty'])
def test_identity_contract(reader, name, ftype, raw, expected, state):
    rows = [] if state == 'empty' else [(b'*' if state == 'deleted' else b' ') + raw]
    data = bytearray(staffing_columns((name,), rows))
    data[43] = ord(ftype)
    if ftype not in ('N', 'F'):
        with pytest.raises(reader.DBFStructureError):
            reader.read_dbf_buffer(bytes(data), identity_fields=(name,))
    elif state == 'active' and expected is None:
        with pytest.raises(reader.DBFValueError):
            reader.read_dbf_buffer(bytes(data), identity_fields=(name,))
    else:
        result = reader.read_dbf_buffer(bytes(data), identity_fields=(name,))
        assert result == ([{name: expected}] if state == 'active' else [])
        if result:
            assert type(result[0][name]) is int


def test_opt_in_and_file_errors(reader, tmp_path):
    data = bytearray(staffing_columns(('GROUPID',), [b'    T']))
    data[43] = ord('L')
    assert reader.read_dbf_buffer(bytes(data)) == [{'GROUPID': True}]
    path = tmp_path / 'missing.dbf'
    assert reader.read_dbf(str(path)) == []
    with pytest.raises(reader.DBFReadError):
        reader.read_dbf(str(path), identity_fields=('GROUPID',))
    path.write_bytes(bytes(data))
    with pytest.raises(reader.DBFStructureError):
        reader.read_dbf(str(path), identity_fields=('GROUPID',))


@pytest.mark.parametrize('ftype', ['N', 'F'])
@pytest.mark.parametrize('raw,expected', [
    (b'9007199254740993.0', 9007199254740993),
    (b'-9007199254740993.0', -9007199254740993),
    (b'1.0000000000000001', None),
    (b'9007199254740992.5', None),
    (b'0.0000000000000000000000000000000000001', None),
    (b'-0.0000000000000000', 0),
])
def test_exact_decimal_identity(reader, ftype, raw, expected):
    data = bytearray(staffing_columns(('GROUPID',), [b' ' + raw]))
    struct.pack_into('<H', data, 10, 1 + len(raw))
    data[43] = ord(ftype)
    data[48] = len(raw)
    data[49] = 1
    if expected is None:
        with pytest.raises(reader.DBFValueError, match='invalid_required_identity'):
            reader.read_dbf_buffer(bytes(data), identity_fields=('GROUPID',))
    else:
        assert reader.read_dbf_buffer(bytes(data), identity_fields=('GROUPID',)) == [
            {'GROUPID': expected}]


@pytest.mark.parametrize('fields', [(), ('GROUPID', 'GROUPID')])
def test_missing_duplicate_identity_descriptor(reader, fields):
    with pytest.raises(reader.DBFStructureError):
        reader.read_dbf_buffer(staffing_columns(fields), identity_fields=('GROUPID',))


def check_identity_api(http, headers, prefix, root, database):
    from tools.test_upstream_staffing_temporal_app import calendar_payload
    from tools.test_upstream_staffing_source_contract import assert_source_error

    for table, suffix in [('SHDEM', ''), ('SPDEM', '/special')]:
        path = root / f'5{table}.DBF'
        for index in (2, 3, 4):
            for ftype, raw, category in [('L', b'   T', 'structure'),
                                         ('M', b'0001', 'structure'),
                                         ('N', b' 1.5', 'numeric_value'),
                                         ('F', b' 1.0', None)]:
                data = bytearray(calendar_payload(table, 'active', 'valid'))
                data[32 + index * 32 + 11] = ord(ftype)
                start = int.from_bytes(data[8:10], 'little') + 1 + index * 4
                data[start:start + 4] = raw
                path.write_bytes(data)
                database(str(root))._read(table)  # Warm permissive cache first.
                for query in ('', '?group_id=1', '?group_id=999'):
                    response = http.get(prefix + '/staffing-requirements' + suffix + query,
                                        headers=headers)
                    if category:
                        assert response.status_code == 500
                        assert_source_error(response, category)
                    else:
                        assert response.status_code == 200
                path.write_bytes(calendar_payload(table, 'active', 'valid'))
                assert http.get(prefix + '/staffing-requirements' + suffix,
                                headers=headers).status_code == 200
