"""Isolated strict-reader candidate; only generated synthetic DBF bytes.

SP5_STRICT_READER points at the patched Library dbf_reader.py.
"""
import importlib.util
import os
import struct

import pytest

from test_upstream_source_read_integrity import synthetic_dbf


@pytest.fixture
def reader():
    spec = importlib.util.spec_from_file_location('strict_reader', os.environ['SP5_STRICT_READER'])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('records,expected', [([], []), ([b' 0010'], [{'ID': 10}]),
                                            ([b'*0020', b' 0010'], [{'ID': 10}])])
def test_valid_including_deleted(reader, records, expected):
    assert reader.read_dbf_buffer(synthetic_dbf(records), strict=True) == expected


@pytest.mark.parametrize('payload,code', [
    (b'', 'short_header'), (b'x' * 31, 'short_header'),
    (synthetic_dbf([], declared=1), 'truncated_records'),
    (synthetic_dbf([b' 0010'], declared=2) + b' 0', 'truncated_records'),
    (synthetic_dbf([b'!0010']), 'invalid_deletion_marker'),
])
def test_rejects_without_partial_result(reader, payload, code):
    with pytest.raises(reader.DBFStructureError) as error:
        reader.read_dbf_buffer(payload, strict=True)
    assert error.value.code == code
    assert str(error.value) == code


@pytest.mark.parametrize('offset,value,code', [
    (8, 32, 'invalid_header_size'), (8, 1000, 'invalid_header_size'),
    (10, 0, 'invalid_record_size'), (10, 6, 'record_width_mismatch'),
])
def test_bad_sizes(reader, offset, value, code):
    data = bytearray(synthetic_dbf())
    struct.pack_into('<H', data, offset, value)
    with pytest.raises(reader.DBFStructureError, match=code):
        reader.read_dbf_buffer(bytes(data), strict=True)


def test_missing_terminator(reader):
    data = bytearray(synthetic_dbf())
    data[64] = 0
    with pytest.raises(reader.DBFStructureError, match='truncated_field_descriptor'):
        reader.read_dbf_buffer(bytes(data), strict=True)


def test_header_padding_and_optional_eof(reader):
    data = bytearray(synthetic_dbf([b' 0010']))
    struct.pack_into('<H', data, 8, 328)
    data[65:65] = bytes(263)
    assert reader.read_dbf_buffer(bytes(data) + b'\x1a', strict=True) == [{'ID': 10}]


def test_legacy_default_unchanged(reader):
    assert reader.read_dbf_buffer(b'') == []
    assert reader.read_dbf_buffer(synthetic_dbf([b' 0010'], declared=2)) == [{'ID': 10}]
