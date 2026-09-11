"""Synthetic native person identities, run inside the rebuilt Library package."""
import pytest

from tools.test_upstream_staffing_source_contract import staffing_columns


def check_person_reader(root):
    from sp5lib.database import SP5Database
    from sp5lib.dbf_reader import DBFStructureError, DBFValueError

    root.mkdir()
    db = SP5Database(str(root), strict_staffing=True)
    plain = SP5Database(str(root))
    for table, fields in [('GRASG', ('GROUPID', 'EMPLOYEEID')), ('EMPL', ('ID',))]:
        path = root / f'5{table}.DBF'
        for index, field in enumerate(fields):
            for raw, field_type, valid in [
                (b'0001', 'N', True), (b' 1.0', 'N', True),
                (b' 1.0', 'F', True), (b' 1.5', 'N', False),
                (b'   T', 'L', False), (b'0001', 'C', False),
                (b'    ', 'N', False), (b'nope', 'N', False),
            ]:
                values = [b'0001'] * len(fields)
                values[index] = raw
                data = bytearray(staffing_columns(fields, [b' ' + b''.join(values)]))
                data[32 + 32 * index + 11] = ord(field_type)
                path.write_bytes(data)
                # Prime permissive cache: strict access must not reuse it.
                plain._read(table)
                if valid:
                    rows = db._read(table)
                    assert rows[0][field] == 1 and type(rows[0][field]) is int
                    if table == 'GRASG':
                        assert db.get_group_members(1) == [1]
                        assert db.get_all_group_members() == {1: [1]}
                    else:
                        assert db.get_employees(include_hidden=True)[0]['ID'] == 1
                else:
                    for read in [lambda: db._read(table),
                                 (lambda: db.get_group_members(1)) if table == 'GRASG'
                                 else (lambda: db.get_employees(include_hidden=True))]:
                        with pytest.raises((DBFStructureError, DBFValueError)) as error:
                            read()
                        assert str(root) not in str(error.value)
                # A failed source read must not poison subsequent valid reads.
                path.write_bytes(staffing_columns(fields, [b' ' + b'0001' * len(fields)]))
                assert db._read(table)[0][field] == 1
            path.write_bytes(staffing_columns(tuple(f for f in fields if f != field)))
            with pytest.raises(DBFStructureError):
                db._read(table)
