"""Rebuild the combined candidate from tracked source and checked-in patches.

Explicit gate: SP5_LIBRARY_SOURCE and SP5_API_SOURCE point at clean upstream
checkouts. No prepared /tmp module overrides, DBF files, .env or upstream state
are used. Real API deployment and credential login are outside this gate.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_packaged_staffing_runtime(tmp_path, prefix):
    code = tmp_path / 'code'
    code.mkdir(mode=0o700)
    for variable, package in [('SP5_LIBRARY_SOURCE', 'sp5lib'),
                              ('SP5_API_SOURCE', 'sp5api')]:
        checkout = Path(os.environ[variable])
        dirty = subprocess.run(
            ['git', '-C', str(checkout), 'status', '--porcelain',
             '--untracked-files=no', '--', package],
            check=True, capture_output=True, text=True).stdout
        assert not dirty, f'{package}: candidate gate requires clean tracked source'
        sources = subprocess.run(
            ['git', '-C', str(checkout), 'ls-files', '-z', '--', package],
            check=True, capture_output=True).stdout.decode().split('\0')
        for name in sources:
            if not name.endswith('.py'):
                continue
            source = checkout / name
            assert not source.is_symlink()
            target = code / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        assert (code / package / '__init__.py').is_file()
    patches = [
        'upstream-library-strict-reader-candidate.patch',
        'upstream-library-temporal-reader-candidate.patch',
        'upstream-library-staffing-activation-candidate.patch',
        'upstream-library-staffing-temporal-activation-candidate.patch',
        'upstream-api-staffing-source-contract-candidate.patch',
        'upstream-api-staffing-activation-candidate.patch',
    ]
    for name in patches:
        subprocess.run(['git', 'apply', str(Path(__file__).parent.resolve() / name)],
                       cwd=code, check=True, capture_output=True, text=True)
    backend = tmp_path / 'backend'
    backend.mkdir(mode=0o700)
    env = {
        'PATH': os.defpath,
        'PYTHONPATH': os.pathsep.join([str(code), str(Path.cwd()),
                                     str(Path.cwd() / 'tools'), str(Path.cwd() / 'tests')]),
        'SP5_BACKEND_DIR': str(backend), 'SP5_DB_PATH': str(backend),
        'SP5_STATE_DIR': str(backend / 'state'), 'DB_BACKEND': 'dbf',
        'SP5_READONLY': 'true', 'SP5_DEV_MODE': 'false',
        'LOG_FILE': str(backend / 'api.log'),
        'SP5_AUDIT_LOG': str(backend / 'audit.json'),
        'SP5_PACKAGED_RUNTIME': str(code), 'SP5_TEMPORAL_ACTIVATION': '1',
        'SP5_STAFFING_DATABASE': str(code / 'sp5lib/database.py'),
    }
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).with_name('test_upstream_staffing_full_app.py')),
         prefix], cwd=backend, env=env, capture_output=True, text=True, timeout=90)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert 'full-app contract passed' in completed.stdout
