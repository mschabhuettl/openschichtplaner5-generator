"""Characterize original Library reads with synthetic DBF bytes, no real data.

These assertions expose the current permissive behavior, not a safe contract.
Run with the original Library checkout on PYTHONPATH.
"""
import struct

import pytest

from sp5lib.database import SP5Database
from sp5lib.dbf_reader import read_dbf_buffer


def synthetic_dbf(records=(), *, declared=None):
    header = bytearray(32)
    header[0] = 3
    struct.pack_into('<IHH', header, 4,
                     len(records) if declared is None else declared, 65, 5)
    field = bytearray(32)
    field[:2] = b'ID'
    field[11] = ord('N')
    field[16] = 4
    return bytes(header + field) + b'\r' + b''.join(records)


def test_missing_file_and_valid_empty_table_have_same_result(tmp_path, caplog):
    db = SP5Database(str(tmp_path))
    assert db._read('MASHI') == []
    assert 'DBF read error' in caplog.text
    (tmp_path / '5MASHI.DBF').write_bytes(synthetic_dbf())
    caplog.clear()
    assert db._read('MASHI') == []
    assert not caplog.records


@pytest.mark.parametrize('payload', [b'', b'\x03' * 31])
def test_short_header_is_cached_as_empty_without_error(tmp_path, caplog, payload):
    (tmp_path / '5MASHI.DBF').write_bytes(payload)
    db = SP5Database(str(tmp_path))
    first = db._read('MASHI')
    assert first == []
    assert db._read('MASHI') is first
    assert not caplog.records


@pytest.mark.parametrize('tail', [b'', b'  0'])
def test_truncated_records_are_cached_as_successful_prefix(tmp_path, caplog, tail):
    payload = synthetic_dbf([b' 0010'], declared=2) + tail
    (tmp_path / '5MASHI.DBF').write_bytes(payload)
    db = SP5Database(str(tmp_path))
    first = db._read('MASHI')
    assert first == [{'ID': 10}]
    assert db._read('MASHI') is first
    assert not caplog.records


def test_deleted_records_are_legitimately_absent_from_parsed_count():
    # len(parsed) != header count is NOT sufficient evidence of truncation.
    assert read_dbf_buffer(synthetic_dbf([b' 0010', b'*0020'])) == [{'ID': 10}]


def test_same_size_same_mtime_replacement_keeps_stale_cache(tmp_path):
    import os

    path = tmp_path / '5MASHI.DBF'
    path.write_bytes(synthetic_dbf([b' 0010']))
    db = SP5Database(str(tmp_path))
    assert db._read('MASHI') == [{'ID': 10}]
    before = path.stat()
    path.write_bytes(synthetic_dbf([b' 0020']))
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert read_dbf_buffer(path.read_bytes()) == [{'ID': 20}]
    assert db._read('MASHI') == [{'ID': 10}]
