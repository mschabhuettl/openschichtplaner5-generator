"""Synthetic full API middleware contract; no lifespan/background services/login.

Run explicitly with SP5_API_SOURCE, SP5_STAFFING_ROUTER and SP5_STRICT_READER.
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


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_full_app_staffing_contract(tmp_path, prefix):
    package = Path(os.environ['SP5_API_SOURCE']) / 'sp5api'
    for source in package.rglob('*.py'):
        target = tmp_path / 'code' / 'sp5api' / source.relative_to(package)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    shutil.copyfile(os.environ['SP5_STAFFING_ROUTER'],
                    tmp_path / 'code/sp5api/routers/master_data.py')
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
    completed = subprocess.run([sys.executable, str(Path(__file__).resolve()), prefix],
                               cwd=backend, env=env, capture_output=True, text=True, timeout=90)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert 'full-app contract passed' in completed.stdout


def run_contract(prefix):
    import importlib.util
    spec = importlib.util.spec_from_file_location('sp5lib.dbf_reader',
                                                  os.environ['SP5_STRICT_READER'])
    reader = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = reader
    spec.loader.exec_module(reader)
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
                                   numeric_fields=('MIN', 'MAX'))
        return original_read(self, table)

    SP5Database._read = strict_read
    root = Path(os.environ['SP5_DB_PATH'])
    for table in ('SHDEM', 'SPDEM', 'DADEM', 'SHIFT', 'WOPL'):
        (root / f'5{table}.DBF').write_bytes(staffing_columns(('MIN', 'MAX')))
    # Deliberately no TestClient context manager: startup runs independent
    # migrations/schedulers, outside the HTTP/auth/source contract under test.
    http = TestClient(app, raise_server_exceptions=False)
    token = 'synthetic-only-session'
    _sessions[token] = {'ID': 999, 'NAME': 'synthetic', 'role': 'Leser',
                        'ADMIN': False, 'RIGHTS': 1}
    headers = {'X-Auth-Token': token}
    try:
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
                (staffing_columns(('MIN', 'MAX'), [b' 0000    ']), 'numeric_value'),
                (None, 'read'),
                (staffing_columns(('MIN', 'MAX'), [b' 0000  -1']), None),
                (staffing_columns(('MIN', 'MAX')), None),
            ]:
                if payload is None:
                    path.unlink()
                else:
                    path.write_bytes(payload)
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
        del _sessions[token]
        assert http.get(url, headers=headers).status_code == 401
    finally:
        http.close()
        _sessions.pop(token, None)
    print('full-app contract passed')


if __name__ == '__main__':
    run_contract(sys.argv[1])
