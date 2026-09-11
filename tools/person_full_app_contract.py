"""Synthetic person join through actual API middleware and Generator transport."""
from io import BytesIO
from urllib.error import HTTPError
from urllib.parse import urlsplit

import pytest


def check_person_join(http, headers, prefix):
    from sp5api.routers import employees as router
    from sp5generator.api_adapter import APIClient, APIImportError

    record = {'ID': 101, 'NAME': 'PRIVATE_SENTINEL', 'HRSWEEK': 40}
    rows, members = [record], [101]

    class Database:
        def get_employees(self, **kw):
            return rows

        def get_group_members(self, group_id):
            return members

    class Transport:
        def open(self, request, **kw):
            response = http.get(urlsplit(request.full_url).path, headers=headers)
            if response.status_code >= 400:
                raise HTTPError(request.full_url, response.status_code, 'failure',
                                response.headers, BytesIO(response.content))
            return BytesIO(response.content)

    original = router.get_db
    router.get_db = Database
    url = prefix + '/groups/1/members'
    try:
        assert http.get(url).status_code == 401
        for case in ('orphan', 'conflict', 'invalid', 'valid'):
            rows[:] = [record]
            members[:] = [101]
            if case == 'orphan':
                members.append(102)
            if case == 'conflict':
                rows.append({**record, 'HRSWEEK': 12})
            if case == 'invalid':
                members[:] = [True]
            api = object.__new__(APIClient)
            api.base, api.headers, api.cache = 'http://synthetic.test', {}, {}
            api.opener = Transport()
            response = http.get(url, headers=headers)
            if case == 'valid':
                assert response.status_code == 200
                assert api.get(url) == [record]
            else:
                assert response.status_code == 500
                assert response.headers['X-SP5-Error-Code'] == 'employee_source_unresolved'
                assert response.headers['X-SP5-Error-Category'] == (
                    'invalid_person_identity' if case == 'invalid' else
                    'orphan_membership' if case == 'orphan' else 'conflicting_employee')
                assert 'PRIVATE_SENTINEL' not in response.text
                assert '101' not in response.text and '102' not in response.text
                with pytest.raises(APIImportError, match='HTTP 500') as caught:
                    api.get(url)
                assert 'Personalquelle in SP5 prüfen' in str(caught.value)
                assert 'PRIVATE_SENTINEL' not in str(caught.value)
                assert api.cache == {}
    finally:
        router.get_db = original


def check_native_person_source(http, headers, prefix, root):
    """Real DBF -> strict Library -> API middleware -> Generator transport."""
    from sp5api.routers import employees as router
    from sp5lib.database import SP5Database
    from sp5generator.api_adapter import APIClient, APIImportError
    from tools.test_upstream_staffing_source_contract import staffing_columns

    root.mkdir()
    db = SP5Database(str(root), strict_staffing=True)
    original = router.get_db
    router.get_db = lambda: db
    url = prefix + '/groups/1/members'

    class Transport:
        def open(self, request, **kw):
            response = http.get(urlsplit(request.full_url).path, headers=headers)
            if response.status_code >= 400:
                raise HTTPError(request.full_url, response.status_code, 'failure',
                                response.headers, BytesIO(response.content))
            return BytesIO(response.content)

    try:
        assert http.get(url).status_code == 401
        for table, field_index in [('GRASG', 0), ('GRASG', 1), ('EMPL', 0)]:
            for raw, field_type in [(b' 1.5', 'N'), (b'   T', 'L'), (b'0001', 'C')]:
                for name, fields in [('GRASG', ('GROUPID', 'EMPLOYEEID')),
                                     ('EMPL', ('ID',))]:
                    values = [b'0001'] * len(fields)
                    if name == table:
                        values[field_index] = raw
                    data = bytearray(staffing_columns(fields, [b' ' + b''.join(values)]))
                    if name == table:
                        data[32 + 32 * field_index + 11] = ord(field_type)
                    (root / f'5{name}.DBF').write_bytes(data)
                response = http.get(url, headers=headers)
                # Current middleware provides only a generic 500 here. This is
                # not yet the category-specific employee source contract.
                assert response.status_code == 500
                assert str(root) not in response.text
                assert 'Traceback' not in response.text
                api = object.__new__(APIClient)
                api.base, api.headers, api.cache = 'http://synthetic.test', {}, {}
                api.opener = Transport()
                with pytest.raises(APIImportError, match='HTTP 500'):
                    api.get(url)
                assert api.cache == {}
        for name, fields in [('GRASG', ('GROUPID', 'EMPLOYEEID')), ('EMPL', ('ID',))]:
            (root / f'5{name}.DBF').write_bytes(
                staffing_columns(fields, [b' ' + b' 1.0' * len(fields)]))
        response = http.get(url, headers=headers)
        assert response.status_code == 200
        assert [row['ID'] for row in response.json()] == [1]
    finally:
        router.get_db = original
