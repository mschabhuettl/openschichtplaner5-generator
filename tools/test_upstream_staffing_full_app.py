"""Synthetic full API middleware contract; no lifespan/background services/login.

Run explicitly with SP5_API_SOURCE, SP5_STAFFING_ROUTER and SP5_STRICT_READER.
Candidate activation additionally needs SP5_STAFFING_DATABASE and
SP5_STAFFING_DEPENDENCIES; temporal mode needs SP5_TEMPORAL_DATABASE and
the temporal reader/API candidates. Injected mode remains the comparison baseline.
When combining with test_upstream_staffing_source_contract.py, also set
SP5_OSP5_FRONTEND to the OSP5 frontend checkout (its consumer checks require it).
Only Python source is copied, never upstream fixtures, .env or state. The child
uses a fresh environment and private backend. Session injection exercises auth
validation, not credential login. The strict reader remains an opt-in candidate.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.mark.parametrize('activation', ['injected', 'candidate', 'temporal'])
@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_full_app_staffing_contract(tmp_path, prefix, activation):
    package = Path(os.environ['SP5_API_SOURCE']) / 'sp5api'
    for source in package.rglob('*.py'):
        target = tmp_path / 'code' / 'sp5api' / source.relative_to(package)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    shutil.copyfile(os.environ['SP5_STAFFING_ROUTER'],
                    tmp_path / 'code/sp5api/routers/master_data.py')
    if activation in ('candidate', 'temporal'):
        shutil.copyfile(os.environ['SP5_STAFFING_DEPENDENCIES'],
                        tmp_path / 'code/sp5api/dependencies.py')
    backend = tmp_path / 'backend'
    backend.mkdir(mode=0o700)
    env = {
        'PATH': os.defpath,
        'PYTHONPATH': os.pathsep.join([str(tmp_path / 'code'), str(Path.cwd()),
                                     str(Path.cwd() / 'tools'), str(Path.cwd() / 'tests')]),
        'SP5_BACKEND_DIR': str(backend), 'SP5_DB_PATH': str(backend),
        'SP5_STATE_DIR': str(backend / 'state'), 'DB_BACKEND': 'dbf',
        'SP5_READONLY': 'true', 'SP5_DEV_MODE': 'false',
        'LOG_FILE': str(backend / 'api.log'),
        'SP5_AUDIT_LOG': str(backend / 'audit.json'),
        'SP5_STRICT_READER': os.environ['SP5_STRICT_READER'],
    }
    if activation in ('candidate', 'temporal'):
        env['SP5_STAFFING_DATABASE'] = os.environ[
            'SP5_TEMPORAL_DATABASE' if activation == 'temporal' else 'SP5_STAFFING_DATABASE']
    if activation == 'temporal':
        env['SP5_TEMPORAL_ACTIVATION'] = '1'
    completed = subprocess.run([sys.executable, str(Path(__file__).resolve()), prefix],
                               cwd=backend, env=env, capture_output=True, text=True, timeout=90)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert 'full-app contract passed' in completed.stdout


def run_contract(prefix):
    import importlib.util
    if os.environ.get('SP5_PACKAGED_RUNTIME'):
        import sp5lib.dbf_reader as reader
        import sp5lib.database as database
        import sp5api.dependencies as dependencies
        import sp5api.routers.master_data as router
        code = Path(os.environ['SP5_PACKAGED_RUNTIME']).resolve()
        for module in (reader, database, dependencies, router):
            assert Path(module.__file__).resolve().is_relative_to(code)
    else:
        spec = importlib.util.spec_from_file_location('sp5lib.dbf_reader',
                                                  os.environ['SP5_STRICT_READER'])
        reader = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = reader
        spec.loader.exec_module(reader)
    if 'SP5_STAFFING_DATABASE' in os.environ and not os.environ.get('SP5_PACKAGED_RUNTIME'):
        spec = importlib.util.spec_from_file_location('sp5lib.database',
                                                      os.environ['SP5_STAFFING_DATABASE'])
        database = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = database
        spec.loader.exec_module(database)
    from sp5lib.database import SP5Database
    from test_upstream_staffing_source_contract import staffing_columns, assert_source_error
    from fastapi.testclient import TestClient
    from sp5api.main import app, _sessions
    from sp5generator.api_adapter import APIClient, APIImportError
    from io import BytesIO
    from urllib.error import HTTPError
    from urllib.parse import urlsplit

    original_read = SP5Database._read

    def strict_read(self, table):
        if table in ('SHDEM', 'SPDEM'):
            return reader.read_dbf(self._table(table), strict=True,
                                   numeric_fields=('MIN', 'MAX'),
                                   required_fields=('GROUPID', 'SHIFTID', 'WORKPLACID'))
        return original_read(self, table)

    if 'SP5_STAFFING_DATABASE' not in os.environ:
        SP5Database._read = strict_read
    else:
        # The full app's real get_db factory activates the constructor opt-in.
        from sp5api.dependencies import get_db
        assert get_db().strict_staffing is True
        assert SP5Database(os.environ['SP5_DB_PATH']).strict_staffing is False
    fields = ('MIN', 'MAX', 'GROUPID', 'SHIFTID', 'WORKPLACID')
    root = Path(os.environ['SP5_DB_PATH'])
    for table in ('SHDEM', 'SPDEM', 'DADEM', 'SHIFT', 'WOPL'):
        (root / f'5{table}.DBF').write_bytes(staffing_columns(fields))
    # Deliberately no TestClient context manager: startup runs independent
    # migrations/schedulers, outside the HTTP/auth/source contract under test.
    http = TestClient(app, raise_server_exceptions=False)
    token = 'synthetic-only-session'
    _sessions[token] = {'ID': 999, 'NAME': 'synthetic', 'role': 'Leser',
                        'ADMIN': False, 'RIGHTS': 1}
    headers = {'X-Auth-Token': token}
    try:
        if os.environ.get('SP5_TEMPORAL_ACTIVATION'):
            from test_upstream_staffing_temporal_app import check_temporal
            check_temporal(http, headers, prefix, root, SP5Database, APIClient, APIImportError)
            if os.environ.get('SP5_IDENTITY_ACTIVATION'):
                from tools.test_upstream_identity_reader import check_identity_api
                check_identity_api(http, headers, prefix, root, SP5Database)
            if os.environ.get('SP5_PERSON_ACTIVATION'):
                from person_full_app_contract import check_person_join
                check_person_join(http, headers, prefix)
            del _sessions[token]
            assert http.get(prefix + '/staffing-requirements', headers=headers).status_code == 401
            print('full-app contract passed')
            return
        for table, suffix in [('SHDEM', ''), ('SPDEM', '/special')]:
            url = prefix + '/staffing-requirements' + suffix
            assert http.get(url).status_code == 401
            assert http.get(url, headers={'X-Auth-Token': 'invalid'}).status_code == 401
            path = root / f'5{table}.DBF'

            class ASGITransport:
                def open(self, request, **kwargs):
                    response = http.get(urlsplit(request.full_url).path, headers=headers)
                    if response.status_code >= 400:
                        raise HTTPError(request.full_url, response.status_code, 'source failure',
                                        response.headers, BytesIO(response.content))
                    return BytesIO(response.content)

            api = object.__new__(APIClient)
            api.base, api.headers, api.cache = 'http://synthetic.test', {}, {}
            api.opener = ASGITransport()
            for payload, category in [
                (staffing_columns(('MIN',)), 'structure'),
                (staffing_columns(fields, [b' 0000    000100010001']), 'numeric_value'),
                (None, 'read'),
                (staffing_columns(fields, [b' 0000  -1000100010001']), None),
                (staffing_columns(fields), None),
            ]:
                if payload is None:
                    path.unlink()
                else:
                    path.write_bytes(payload)
                if 'SP5_STAFFING_DATABASE' in os.environ and payload is not None:
                    # Warm the shared permissive cache with the exact same bytes.
                    # Strict activation must not trust that unvalidated parse.
                    SP5Database(str(root))._read(table)
                response = http.get(url, headers=headers)
                if category:
                    assert response.status_code == 500, response.text
                    assert_source_error(response, category)
                    assert str(root) not in response.text
                    with pytest.raises(APIImportError, match='HTTP 500'):
                        api.get(url)
                    assert api.cache == {}
                else:
                    assert response.status_code == 200, response.text
                    # First success after three failures must really reread.
                    if not api.cache:
                        assert api.get(url) == response.json()
                    rows = response.json() if suffix else response.json()['shift_requirements']
                    if rows:
                        assert rows[0]['min'] == 0 and rows[0]['max'] == -1
                    else:
                        assert rows == []
                assert ('deprecation' in response.headers) == (prefix == '/api')
            # Structural identity loss must fail before team filtering, even
            # with a permissively warmed cache and empty/deleted-only tables.
            for missing in ('GROUPID', 'SHIFTID', 'WORKPLACID'):
                remaining = tuple(field for field in fields if field != missing)
                for records in ([], [b' ' + b'0001' * len(remaining)],
                                [b'*' + b'0001' * len(remaining)]):
                    path.write_bytes(staffing_columns(remaining, records))
                    if 'SP5_STAFFING_DATABASE' in os.environ:
                        SP5Database(str(root))._read(table)
                    for query in ('', '?group_id=1'):
                        response = http.get(url + query, headers=headers)
                        assert response.status_code == 500, response.text
                        assert_source_error(response, 'structure')
            for duplicate in ('GROUPID', 'SHIFTID', 'WORKPLACID'):
                duplicated = (*fields, duplicate)
                path.write_bytes(staffing_columns(duplicated))
                if 'SP5_STAFFING_DATABASE' in os.environ:
                    SP5Database(str(root))._read(table)
                response = http.get(url + '?group_id=1', headers=headers)
                assert response.status_code == 500, response.text
                assert_source_error(response, 'structure')
            # Explicit identities and valid empty/deleted tables remain valid.
            for records in ([], [b' 0000  -1000100010001'],
                            [b'*0000  -1000100010001']):
                path.write_bytes(staffing_columns(fields, records))
                response = http.get(url + '?group_id=1', headers=headers)
                assert response.status_code == 200, response.text
                rows = response.json() if suffix else response.json()['shift_requirements']
                if records and records[0][:1] == b' ':
                    assert len(rows) == 1
                    assert all(rows[0][key] == 1 for key in
                               ('group_id', 'shift_id', 'workplace_id'))
                else:
                    assert rows == []
        del _sessions[token]
        assert http.get(url, headers=headers).status_code == 401
    finally:
        http.close()
        _sessions.pop(token, None)
    print('full-app contract passed')


if __name__ == '__main__':
    run_contract(sys.argv[1])
