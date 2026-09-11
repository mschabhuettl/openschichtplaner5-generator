"""Calendar activation assertions used by the isolated full-app child.

Only synthetic DBF bytes. Requires both strict and temporal reader candidates,
plus SP5_TEMPORAL_DATABASE with both staffing activation patches applied.
"""
from io import BytesIO
import struct
from urllib.error import HTTPError
from urllib.parse import urlsplit

import pytest

from tools.test_upstream_staffing_source_contract import assert_source_error, staffing_columns


def calendar_payload(table, state, kind):
    field = 'DATE' if table == 'SPDEM' else 'WEEKDAY'
    ftype, raw = ({'valid': ('D', b'20260901'), 'blank': ('D', b'        '),
                   'invalid': ('D', b'20260230'), 'wrong_type': ('N', b'20260901')}
                  if table == 'SPDEM' else
                  {'valid': ('N', b'0007'), 'blank': ('N', b'    '),
                   'invalid': ('N', b'0008'), 'wrong_type': ('D', b'20260901')})[kind]
    fields = ('MIN', 'MAX', 'GROUPID', 'SHIFTID', 'WORKPLACID', field)
    data = bytearray(staffing_columns(fields))
    data[32 + 5 * 32 + 11] = ord(ftype)
    data[32 + 5 * 32 + 16] = len(raw)
    records = [] if state == 'empty' else [
        (b'*' if state == 'deleted' else b' ') + b'0001' * 5 + raw]
    struct.pack_into('<I', data, 4, len(records))
    struct.pack_into('<H', data, 10, 21 + len(raw))
    return bytes(data) + b''.join(records)


def check_temporal(http, headers, prefix, root, database, api_type, import_error):
    class Transport:
        def open(self, request, **kwargs):
            parsed = urlsplit(request.full_url)
            response = http.get(parsed.path + ('?' + parsed.query if parsed.query else ''),
                                headers=headers)
            if response.status_code >= 400:
                raise HTTPError(request.full_url, response.status_code, 'source failure',
                                response.headers, BytesIO(response.content))
            return BytesIO(response.content)

    for table, suffix in [('SHDEM', ''), ('SPDEM', '/special')]:
        url = prefix + '/staffing-requirements' + suffix
        path = root / f'5{table}.DBF'
        for state in ('active', 'empty', 'deleted'):
            for kind in ('invalid', 'blank', 'wrong_type', 'valid'):
                path.write_bytes(calendar_payload(table, state, kind))
                # Deliberately warm the permissive shared Library cache first.
                database(str(root))._read(table)
                for query in ('', '?group_id=1&date=2026-09-01',
                              '?group_id=999&date=2026-09-02'):
                    assert http.get(url + query).status_code == 401
                    assert http.get(url + query, headers={'X-Auth-Token': 'invalid'}).status_code == 401
                    api = object.__new__(api_type)
                    api.base, api.headers, api.cache = 'http://synthetic.test', {}, {}
                    api.opener = Transport()
                    response = http.get(url + query, headers=headers)
                    bad = kind == 'wrong_type' or (state == 'active' and kind != 'valid')
                    if bad:
                        category = ('structure' if kind == 'wrong_type' else
                                    'numeric_value' if table == 'SHDEM' and kind == 'blank'
                                    else 'temporal_value')
                        assert response.status_code == 500, response.text
                        assert_source_error(response, category)
                        assert str(root) not in response.text
                        with pytest.raises(import_error, match='HTTP 500'):
                            api.get(url + query)
                        assert api.cache == {}
                        # Same client retries after correction: failures must not
                        # cache a fabricated empty staffing response.
                        path.write_bytes(calendar_payload(table, 'active', 'valid'))
                        repaired = api.get(url + query)
                        assert api.cache
                        assert isinstance(repaired, list if suffix else dict)
                        path.write_bytes(calendar_payload(table, state, kind))
                    else:
                        assert response.status_code == 200, response.text
                        assert api.get(url + query) == response.json()
                        rows = response.json() if suffix else response.json()['shift_requirements']
                        if state == 'active' and 'group_id=999' not in query:
                            assert len(rows) == 1
                            assert rows[0]['date' if suffix else 'weekday'] == (
                                '2026-09-01' if suffix else 7)
                        else:
                            assert rows == []
                    assert ('deprecation' in response.headers) == (prefix == '/api')
