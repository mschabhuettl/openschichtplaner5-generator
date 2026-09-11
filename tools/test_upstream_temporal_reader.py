"""Synthetic opt-in calendar contract, layered on the strict reader candidate.

SP5_STRICT_READER must point to a copy with both reader patches applied.
No production configuration or API activation is changed by this candidate.
"""
import importlib.util
import os
import struct

import pytest

from tools.test_upstream_staffing_source_contract import staffing_columns


@pytest.fixture
def reader():
    spec = importlib.util.spec_from_file_location('temporal_reader', os.environ['SP5_STRICT_READER'])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CASES = [
    ('DATE', 'D', b'20260901', None),
    ('DATE', 'D', b'20240229', None),
    ('DATE', 'D', b'20260229', 'invalid_required_date'),
    ('DATE', 'D', b'20260230', 'invalid_required_date'),
    ('DATE', 'D', b'        ', 'invalid_required_date'),
    ('DATE', 'N', b'20260901', 'required_date_column_type'),
    ('WEEKDAY', 'N', b'0000', None),
    ('WEEKDAY', 'N', b'0006', None),
    ('WEEKDAY', 'N', b'0007', None),
    ('WEEKDAY', 'N', b'0008', 'invalid_required_weekday'),
    ('WEEKDAY', 'N', b'  -1', 'invalid_required_weekday'),
    ('WEEKDAY', 'N', b' 1.0', 'invalid_required_weekday'),
    ('WEEKDAY', 'N', b' 1.5', 'invalid_required_weekday'),
    ('WEEKDAY', 'N', b'    ', 'missing_numeric_value'),
    ('WEEKDAY', 'D', b'20260901', 'required_numeric_column_type'),
]


def payload(field, ftype, raw, state):
    data = bytearray(staffing_columns((field,), []))
    data[43] = ord(ftype)
    data[48] = len(raw)
    records = [] if state == 'empty' else [(b'*' if state == 'deleted' else b' ') + raw]
    struct.pack_into('<I', data, 4, len(records))
    struct.pack_into('<H', data, 10, 1 + len(raw))
    return bytes(data) + b''.join(records)


@pytest.mark.parametrize('strict', [False, True])
@pytest.mark.parametrize('state', ['active', 'empty', 'deleted'])
@pytest.mark.parametrize('field,ftype,raw,code', CASES)
def test_calendar_contract(reader, tmp_path, strict, state, field, ftype, raw, code):
    data = payload(field, ftype, raw, state)
    path = tmp_path / 'synthetic.dbf'
    path.write_bytes(data)
    options = {'strict': strict, 'date_fields' if field == 'DATE' else 'weekday_fields': (field,)}
    structural = code and code.startswith('required_')
    error = code if structural or state == 'active' else None
    # File and buffer entry points must preserve the same opt-in contract.
    for read in (lambda: reader.read_dbf(str(path), **options),
                 lambda: reader.read_dbf_buffer(data, **options)):
        if error:
            cls = reader.DBFStructureError if structural else reader.DBFValueError
            with pytest.raises(cls, match=f'^{error}$'):
                read()
        elif state != 'active':
            assert read() == []
        else:
            result = read()
            assert len(result) == 1
            expected = (f'{raw[:4].decode()}-{raw[4:6].decode()}-{raw[6:].decode()}'
                        if field == 'DATE' else int(raw))
            assert result[0][field] == expected
    # Legacy behavior is unchanged without explicit calendar fields.
    assert isinstance(reader.read_dbf_buffer(data), list)


@pytest.mark.parametrize('field,columns', [(field, columns)
    for field in ('DATE', 'WEEKDAY') for columns in ((), ('OTHER',), (field, field))])
def test_missing_or_duplicate_calendar_descriptor(reader, field, columns):
    options = {'strict': True, 'date_fields' if field == 'DATE' else 'weekday_fields': (field,)}
    with pytest.raises(reader.DBFStructureError, match='^required_column_missing_or_duplicate$'):
        reader.read_dbf_buffer(staffing_columns(columns, []), **options)
