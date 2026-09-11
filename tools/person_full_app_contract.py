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
        for case in ('orphan', 'conflict', 'valid'):
            rows[:] = [record]
            members[:] = [101]
            if case == 'orphan':
                members.append(102)
            if case == 'conflict':
                rows.append({**record, 'HRSWEEK': 12})
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
                    'orphan_membership' if case == 'orphan' else 'conflicting_employee')
                assert 'PRIVATE_SENTINEL' not in response.text
                assert '101' not in response.text and '102' not in response.text
                with pytest.raises(APIImportError, match='HTTP 500') as caught:
                    api.get(url)
                assert 'PRIVATE_SENTINEL' not in str(caught.value)
                assert api.cache == {}
    finally:
        router.get_db = original
