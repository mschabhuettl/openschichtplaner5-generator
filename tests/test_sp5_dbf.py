"""New minimal dBASE fixtures exercise the installed library, never external files.

This fixture emitter is test-only. Production DBF access remains in sp5lib.
"""

import struct
from datetime import date
import pytest

pytest.importorskip("sp5lib")
from sp5lib.database import SP5Database
from sp5lib.dbf_reader import get_table_fields
from sp5lib.dbf_writer import append_record
from sp5generator.sp5_adapter import import_snapshot


def empty_table(path, fields):
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


def test_library_reads_new_dbf_need_and_holiday_variant(tmp_path):
    def write(name, fields, records):
        path = tmp_path / f"5{name}.DBF"
        empty_table(path, fields)
        layout = get_table_fields(str(path))
        for record in records:
            append_record(str(path), layout, record)

    ident = [("ID", "N", 8)]
    write(
        "EMPL",
        ident
        + [
            ("NAME", "C", 40),
            ("EMPSTART", "D", 8),
            ("EMPEND", "D", 8),
            ("HRSDAY", "N", 8),
            ("HRSWEEK", "N", 8),
            ("WORKDAYS", "C", 15),
        ],
        [
            {
                "ID": 101,
                "NAME": "Testperson 001",
                "EMPSTART": "2026-01-01",
                "EMPEND": "2026-12-31",
                "HRSDAY": 8,
                "HRSWEEK": 40,
                "WORKDAYS": "1 1 1 1 1 0 0 0",
            }
        ],
    )
    write(
        "GRASG",
        ident + [("EMPLOYEEID", "N", 8), ("GROUPID", "N", 8)],
        [{"ID": 102, "EMPLOYEEID": 101, "GROUPID": 1}],
    )
    write("GROUP", ident + [("NAME", "C", 40)], [{"ID": 1, "NAME": "Team A"}])
    write(
        "SHIFT",
        ident
        + [("NAME", "C", 40)]
        + [(f"STARTEND{i}", "C", 35) for i in range(8)]
        + [(f"DURATION{i}", "N", 8) for i in range(8)],
        [
            {
                "ID": 201,
                "NAME": "Dienst A",
                **{f"STARTEND{i}": "08:00-10:00 11:00-13:00" for i in range(8)},
                **{f"DURATION{i}": 4 for i in range(8)},
            }
        ],
    )
    write("WOPL", ident + [("NAME", "C", 40)], [{"ID": 301, "NAME": "Arbeitsplatz 1"}])
    write(
        "SHDEM",
        ident
        + [
            (key, "N", 8)
            for key in ["GROUPID", "WEEKDAY", "SHIFTID", "WORKPLACID", "MIN", "MAX"]
        ],
        [
            {
                "ID": 401,
                "GROUPID": 1,
                "WEEKDAY": 7,
                "SHIFTID": 201,
                "WORKPLACID": 301,
                "MIN": 1,
                "MAX": 2,
            }
        ],
    )
    write(
        "HOLID",
        ident + [("DATE", "D", 8), ("INTERVAL", "N", 8)],
        [{"ID": 501, "DATE": "2026-01-06", "INTERVAL": 0}],
    )
    # Empty dependent tables are explicit; missing files must not hide fixture assumptions.
    for name in [
        "DADEM",
        "SPDEM",
        "RESTR",
        "MASHI",
        "SPSHI",
        "ABSEN",
        "LEAVT",
        "CYASS",
        "CYCLE",
        "CYENT",
        "CYEXC",
        "WOPAS",
    ]:
        write(name, ident, [])
    write("BOOK", ident + [("EMPLOYEEID", "N", 8), ("DATE", "D", 8),
                            ("TYPE", "N", 8), ("VALUE", "N", 8)], [])
    snapshot = import_snapshot(
        SP5Database(str(tmp_path)), date(2026, 1, 5), date(2026, 1, 6), "1", "UTC"
    )
    assert len(snapshot.employees) == 1
    assert snapshot.employees[0].name == "Testperson 001"
    assert len(snapshot.demands) == 1
    assert (snapshot.demands[0].minimum, snapshot.demands[0].maximum) == (1, 2)
    assert snapshot.shifts[0].holiday
    assert len(snapshot.shifts[0].segments) == 2
    assert snapshot.unresolved
