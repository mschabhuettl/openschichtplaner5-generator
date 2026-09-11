"""Isolated strict-reader candidate; only generated synthetic DBF bytes.

SP5_STRICT_READER points at the patched Library dbf_reader.py.
"""
import importlib.util
import os
import struct
from datetime import date
from pathlib import Path

import pytest

from test_upstream_source_read_integrity import synthetic_dbf
from sp5lib.database import SP5Database
from sp5lib import dbf_writer
from tools.audit_upstream_work_time_plan import load_helpers
from tools.selected_work_segments_candidate import StrictSourceTables, measure_selected


@pytest.fixture
def reader():
    spec = importlib.util.spec_from_file_location('strict_reader', os.environ['SP5_STRICT_READER'])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('plan', ['ist', 'soll'])
@pytest.mark.parametrize('broken', ['MASHI', 'SHIFT', 'ABSEN', 'HOLID'])
@pytest.mark.parametrize('payload,code', [(None, 'file_missing'),
                                       (b'', 'short_header'),
                                       (synthetic_dbf([], declared=1), 'truncated_records')])
def test_strict_failure_reaches_plan_analysis(reader, tmp_path, plan, broken, payload, code):
    for name in ('MASHI', 'SHIFT', 'ABSEN', 'HOLID', 'SPSHI', 'CYCLE',
                 'CYASS', 'CYENT', 'CYEXC'):
        if name != broken:
            (tmp_path / f'5{name}.DBF').write_bytes(synthetic_dbf([]))
    if payload is not None:
        (tmp_path / f'5{broken}.DBF').write_bytes(payload)
    db = SP5Database(str(tmp_path))
    # Prime the actual legacy cache with the misleading empty result.
    assert db._read(broken) == []
    strict = StrictSourceTables(db, reader.read_dbf)
    selector = load_helpers(Path(os.environ['SP5_WORK_TIME_ROUTER']))._employee_plan
    day = date(2026, 1, 5)
    with pytest.raises((reader.DBFReadError, reader.DBFStructureError)) as error:
        measure_selected(strict, selector, 10, day, day, plan, 'Europe/Vienna')
    assert error.value.code == code
    assert str(error.value) == code


@pytest.mark.parametrize('plan', ['ist', 'soll'])
def test_valid_empty_strict_sources_are_not_read_failures(reader, tmp_path, plan):
    for name in ('MASHI', 'SHIFT', 'ABSEN', 'HOLID', 'SPSHI', 'CYCLE',
                 'CYASS', 'CYENT', 'CYEXC'):
        (tmp_path / f'5{name}.DBF').write_bytes(synthetic_dbf([]))
    strict = StrictSourceTables(SP5Database(str(tmp_path)), reader.read_dbf)
    selector = load_helpers(Path(os.environ['SP5_WORK_TIME_ROUTER']))._employee_plan
    day = date(2026, 1, 5)
    assert measure_selected(strict, selector, 10, day, day, plan, 'Europe/Vienna') == ()


@pytest.mark.parametrize('broken', ['SPSHI', 'CYCLE', 'CYASS', 'CYENT', 'CYEXC'])
def test_ist_only_missing_source_does_not_block_soll(reader, tmp_path, broken):
    for name in ('MASHI', 'SHIFT', 'ABSEN', 'HOLID', 'SPSHI', 'CYCLE',
                 'CYASS', 'CYENT', 'CYEXC'):
        if name != broken:
            (tmp_path / f'5{name}.DBF').write_bytes(synthetic_dbf([]))
    strict = StrictSourceTables(SP5Database(str(tmp_path)), reader.read_dbf)
    selector = load_helpers(Path(os.environ['SP5_WORK_TIME_ROUTER']))._employee_plan
    day = date(2026, 1, 5)
    assert measure_selected(strict, selector, 10, day, day, 'soll', 'Europe/Vienna') == ()
    with pytest.raises(reader.DBFReadError, match='^file_missing$'):
        measure_selected(strict, selector, 10, day, day, 'ist', 'Europe/Vienna')


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


def test_strict_file_distinguishes_missing_empty_and_truncated(reader, tmp_path):
    path = tmp_path / 'synthetic.dbf'
    with pytest.raises(reader.DBFReadError) as error:
        reader.read_dbf(str(path), strict=True)
    assert error.value.code == 'file_missing'
    assert str(error.value) == 'file_missing'
    assert reader.read_dbf(str(path)) == []
    path.write_bytes(synthetic_dbf([]))
    assert reader.read_dbf(str(path), strict=True) == []
    path.write_bytes(synthetic_dbf([b' 0010'], declared=2))
    with pytest.raises(reader.DBFStructureError, match='truncated_records'):
        reader.read_dbf(str(path), strict=True)


@pytest.mark.parametrize('failure', [PermissionError, IsADirectoryError, OSError])
def test_unreadable_file_has_source_free_error(reader, monkeypatch, failure):
    def fail(*args, **kwargs):
        raise failure('private source detail must not escape')
    monkeypatch.setattr(reader, 'open', fail, raising=False)
    with pytest.raises(reader.DBFReadError) as error:
        reader.read_dbf('synthetic.dbf', strict=True)
    assert error.value.code == 'file_unreadable'
    assert str(error.value) == 'file_unreadable'
    assert error.value.__suppress_context__
    assert reader.read_dbf('synthetic.dbf') == []


def test_strict_file_rereads_same_size_and_mtime(reader, tmp_path):
    path = tmp_path / 'synthetic.dbf'
    path.write_bytes(synthetic_dbf([b' 0010']))
    before = path.stat()
    assert reader.read_dbf(str(path), strict=True) == [{'ID': 10}]
    path.write_bytes(synthetic_dbf([b' 0020']))
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert reader.read_dbf(str(path), strict=True) == [{'ID': 20}]


@pytest.mark.parametrize('name', [b'MIN', b'MAX', b'WEEKDAY'])
@pytest.mark.parametrize('kind', [b'N', b'F'])
@pytest.mark.parametrize('raw,decimals,code', [
    (b'nope', 0, 'invalid_numeric_value'),
    (b'    ', 0, 'missing_numeric_value'),
    (b'   .', 0, 'missing_numeric_value'),
    (b'\xff000', 0, 'invalid_numeric_value'),
    (b' NaN', 1, 'nonfinite_numeric_value'),
    (b' inf', 1, 'nonfinite_numeric_value'),
])
def test_strict_numeric_source_failure_is_not_zero(reader, name, kind, raw, decimals, code):
    data = bytearray(synthetic_dbf([b' 0001', b' ' + raw]))
    data[32:43] = name.ljust(11, b'\0')
    data[43:44] = kind
    data[49] = decimals
    with pytest.raises(reader.DBFValueError) as error:
        reader.read_dbf_buffer(bytes(data), strict=True)
    assert error.value.code == code
    assert str(error.value) == code
    # A valid prefix must not be returned on numeric source failure.
    assert len(reader.read_dbf_buffer(bytes(data))) == 2


@pytest.mark.parametrize('raw,expected', [(b'0000', 0), (b'  -1', -1),
                                        (b' 1.0', 1.0), (b' 1.5', 1.5)])
def test_strict_reader_preserves_numeric_values_without_staffing_policy(reader, raw, expected):
    data = synthetic_dbf([b' ' + raw])
    assert reader.read_dbf_buffer(data, strict=True) == [{'ID': expected}]
    assert reader.read_dbf_buffer(data) == [{'ID': expected}]


def test_strict_ignores_deleted_numeric_garbage(reader):
    data = synthetic_dbf([b'*nope', b' 0000'])
    assert reader.read_dbf_buffer(data, strict=True) == [{'ID': 0}]


def test_strict_numeric_failure_propagates_through_table_bridge(reader, tmp_path):
    (tmp_path / '5SHDEM.DBF').write_bytes(synthetic_dbf([b' nope']))
    db = SP5Database(str(tmp_path))
    assert db._read('SHDEM') == [{'ID': 0}]
    strict = StrictSourceTables(db, reader.read_dbf)
    with pytest.raises(reader.DBFValueError, match='^invalid_numeric_value$'):
        strict._read('SHDEM')


@pytest.mark.parametrize('value', [None, '', 'invalid'])
@pytest.mark.parametrize('kind', ['N', 'F'])
def test_writer_blank_is_not_evidence_of_corruption(reader, value, kind):
    # The real writer deliberately represents None as spaces, and also uses
    # spaces on conversion failure. Neither reader can recover that origin.
    field = {'name': 'ID', 'type': kind, 'len': 4, 'dec': 0}
    encoded = dbf_writer._encode_field(value, field)
    assert encoded == b'    '
    data = bytearray(synthetic_dbf([b' ' + encoded]))
    data[43] = ord(kind)
    assert reader.read_dbf_buffer(bytes(data)) == [{'ID': 0}]
    with pytest.raises(reader.DBFValueError, match='^missing_numeric_value$'):
        reader.read_dbf_buffer(bytes(data), strict=True)


@pytest.mark.parametrize('record', [{}, {'ID': None}, {'ID': 0}])
def test_actual_append_distinguishes_omitted_numeric_from_explicit_zero(
    reader, tmp_path, monkeypatch, record,
):
    # Local synthetic file only; disable unrelated journal/index side effects.
    path = tmp_path / 'synthetic.dbf'
    path.write_bytes(synthetic_dbf())
    monkeypatch.setattr(dbf_writer, '_after_write', lambda *args, **kwargs: None)
    fields = [{'name': 'ID', 'type': 'N', 'len': 4, 'dec': 0}]
    dbf_writer.append_record(str(path), fields, record)
    assert reader.read_dbf(str(path)) == [{'ID': 0}]
    if record.get('ID') is None:
        assert path.read_bytes()[66:70] == b'    '
        with pytest.raises(reader.DBFValueError, match='^missing_numeric_value$'):
            reader.read_dbf(str(path), strict=True)
    else:
        assert reader.read_dbf(str(path), strict=True) == [{'ID': 0}]


@pytest.mark.parametrize('raw', [b'    ', b'nope', b' NaN'])
def test_structural_failure_takes_precedence_over_unresolved_numbers(reader, raw):
    data = bytearray(synthetic_dbf([b' ' + raw, b'!0000']))
    data[49] = 1
    with pytest.raises(reader.DBFStructureError, match='^invalid_deletion_marker$'):
        reader.read_dbf_buffer(bytes(data), strict=True)


@pytest.mark.parametrize('raw,code', [(b'    ', 'missing_numeric_value'),
                                     (b'nope', 'invalid_numeric_value'),
                                     (b' NaN', 'nonfinite_numeric_value')])
def test_valid_layout_with_unresolved_number_is_not_structural_corruption(reader, raw, code):
    data = bytearray(synthetic_dbf([b' ' + raw]))
    data[49] = 1
    # File layout can be validated independently; it does not certify values.
    reader._validate_dbf_structure(bytes(data))
    with pytest.raises(reader.DBFValueError) as error:
        reader.read_dbf_buffer(bytes(data), strict=True)
    assert not isinstance(error.value, reader.DBFStructureError)
    assert str(error.value) == code


@pytest.mark.parametrize('table,method', [('SHDEM', 'get_staffing_requirements'),
                                         ('SPDEM', 'get_special_staffing')])
@pytest.mark.parametrize('field', ['MIN', 'MAX'])
@pytest.mark.parametrize('raw,code', [(b'0000', None), (b'    ', 'missing_numeric_value'),
                                     (b'nope', 'invalid_numeric_value')])
def test_staffing_library_mapping_preserves_value_failure(reader, tmp_path, monkeypatch,
                                                        table, method, field, raw, code):
    # Actual Library mapping, actual synthetic DBF read, no real source access.
    data = bytearray(synthetic_dbf([b' ' + raw]))
    data[32:43] = field.encode().ljust(11, b'\0')
    (tmp_path / f'5{table}.DBF').write_bytes(bytes(data))
    (tmp_path / '5DADEM.DBF').write_bytes(synthetic_dbf([]))
    db = SP5Database(str(tmp_path))
    monkeypatch.setattr(db, 'get_shifts', lambda **kwargs: [])
    monkeypatch.setattr(db, 'get_workplaces', lambda **kwargs: [])
    legacy = getattr(db, method)()
    rows = legacy['shift_requirements'] if table == 'SHDEM' else legacy
    assert rows[0][field.lower()] == 0
    strict = StrictSourceTables(db, reader.read_dbf)
    monkeypatch.setattr(db, '_read', strict._read)
    if code:
        with pytest.raises(reader.DBFValueError, match=f'^{code}$'):
            getattr(db, method)()
    else:
        assert getattr(db, method)() == legacy
