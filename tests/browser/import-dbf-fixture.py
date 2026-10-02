"""Construct only synthetic DBF source files below the caller-selected temp root."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile

from server import responses
from sp5lib.dbf_reader import get_table_fields
from sp5lib.dbf_writer import append_record
import sp5generator
import sp5lib.database

folder = Path(sys.argv[1]).resolve()
temporary_root = Path(tempfile.gettempdir()).resolve()
assert folder != temporary_root and folder.is_relative_to(temporary_root), "DBF fixture outside temporary root"
assert folder.is_dir() and not any(folder.iterdir()), "DBF fixture requires an existing empty owned directory"

def emit(path, fields):
    header = bytearray(32)
    header[0:4] = bytes([3, 126, 1, 1])
    struct.pack_into(
        "<IHH", header, 4, 0, 33 + 32 * len(fields), 1 + sum(f[2] for f in fields)
    )
    descriptors = bytearray()
    for name, kind, length in fields:
        field = bytearray(32)
        field[: len(name)] = name.encode("ascii")
        field[11] = ord(kind)
        field[16] = length
        descriptors.extend(field)
    path.write_bytes(header + descriptors + b"\r\x1a")


records = {}

def write(name, fields, rows):
    target = folder / f'5{name}.DBF'
    emit(target, fields)
    layout = get_table_fields(str(target))
    for row in rows:
        append_record(str(target), layout, row)
    records[name] = {'fields': fields, 'records': rows}

ident = [('ID', 'N', 8)]
write('EMPL', ident + [('NAME', 'C', 40), ('EMPSTART', 'D', 8), ('EMPEND', 'D', 8)] + [(k, 'N', 8) for k in ['HRSDAY', 'HRSWEEK', 'HRSMONTH', 'CALCBASE']] + [('WORKDAYS', 'C', 15)], responses['/api/employees'])
write('GROUP', ident + [('NAME', 'C', 40), ('SUPERID', 'N', 8)], responses['/api/groups'])
members = [{'ID': gid * 1000 + p['ID'], 'EMPLOYEEID': p['ID'], 'GROUPID': gid} for gid in [1, 2, 3] for p in responses[f'/api/groups/{gid}/members']]
write('GRASG', ident + [('EMPLOYEEID', 'N', 8), ('GROUPID', 'N', 8)], members)
write('SHIFT', ident + [('NAME', 'C', 40)] + [(f'STARTEND{i}', 'C', 35) for i in range(8)] + [(f'DURATION{i}', 'N', 8) for i in range(8)], responses['/api/shifts'])
write('WOPL', ident + [('NAME', 'C', 40)], responses['/api/workplaces'])
write('SHDEM', ident + [(k, 'N', 8) for k in ['GROUPID', 'WEEKDAY', 'SHIFTID', 'WORKPLACID', 'MIN', 'MAX']], [{'ID': row['id'], 'GROUPID': row['group_id'], 'WEEKDAY': row['weekday'], 'SHIFTID': row['shift_id'], 'WORKPLACID': row['workplace_id'], 'MIN': row['min'], 'MAX': row['max']} for row in responses['/api/staffing-requirements']['shift_requirements']])
write('MASHI', ident + [('EMPLOYEEID', 'N', 8), ('DATE', 'D', 8), ('SHIFTID', 'N', 8), ('WORKPLACID', 'N', 8), ('TYPE', 'N', 8)], [{'ID': n, 'EMPLOYEEID': n, 'DATE': '2026-01-12', 'SHIFTID': 201, 'WORKPLACID': 302, 'TYPE': 0} for n in [101, 102, 103]])
write('BOOK', ident + [('EMPLOYEEID', 'N', 8), ('DATE', 'D', 8), ('TYPE', 'N', 8), ('VALUE', 'N', 8)], [])
write('HOLID', ident + [('DATE', 'D', 8), ('INTERVAL', 'N', 8)], [])
for name in ['DADEM', 'SPDEM', 'RESTR', 'SPSHI', 'ABSEN', 'LEAVT', 'CYASS', 'CYCLE', 'CYENT', 'CYEXC', 'WOPAS']:
    write(name, ident, [])

report = {
    'records': records,
    'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())},
    'source_module': sp5generator.__file__,
    'sp5lib_module': sp5lib.database.__file__,
    'sp5lib_sha256': hashlib.sha256(Path(sp5lib.database.__file__).read_bytes()).hexdigest(),
}
print(json.dumps(report, indent=2))
