"""Synthetic route tests for local browser planning and persisted edits."""
import pytest
pytest.importorskip('fastapi')
from fastapi.testclient import TestClient
from sp5generator.webapp import create_app
from sp5generator.solver import solve


def test_local_web_persist_solve_and_export(tmp_path):
    with TestClient(create_app(str(tmp_path), start_worker=False)) as c:
        assert c.get('/').status_code == 200
        from sp5generator import __version__
        assert c.get('/api/version').json() == {'version': __version__, 'auth_enabled': False}
        assert 'OpenSchichtplaner5 Generator' in c.get('/').text
        assert c.get('/static/app.js').status_code == 200
        assert c.get('/static/app.js').headers['Cache-Control'] == 'no-store'
        assert c.get('/api/demo').headers['Cache-Control'] == 'no-store'
        snapshot = c.get('/api/demo').json()
        snapshot['employees'][0]['preferred_kind'] = 'night'
        saved = c.put('/api/snapshots', json=snapshot).json()
        assert saved['revision'] == '1'
        assert c.get('/api/snapshots/'+saved['id']).json()['employees'][0]['preferred_kind'] == 'night'
        saved = c.put('/api/snapshots', json=saved).json()
        assert c.put('/api/snapshots', json=snapshot).status_code == 409
        job = c.post('/api/jobs', json={'snapshot_id': saved['id'], 'time_limit': 3}).json()
        assert job['state'] == 'queued'
        assert c.post('/api/jobs/'+job['id']+'/cancel').json()['state'] == 'cancelled'
        from sp5generator.models import Snapshot
        result = solve(Snapshot.model_validate(saved), time_limit=5)
        assert result.validation.valid and result.validation.complete
        payload = {'snapshot': saved, 'assignments': [a.model_dump(mode='json') for a in result.assignments]}
        assert c.post('/api/validate', json=payload).json()['complete']
        for format in ('json', 'csv', 'xlsx'):
            response = c.post('/api/export/'+format, json=payload)
            assert response.status_code == 200
            assert len(response.content)>100
        payload['assignments'][0]['employee_id']='missing'
        assert not c.post('/api/validate', json=payload).json()['valid']
        assert c.post('/api/export/csv', json=payload).status_code == 422


def test_browser_boundary(tmp_path):
    with TestClient(create_app(str(tmp_path), start_worker=False)) as c:
        assert c.get('/api/demo', headers={'Origin':'https://example.org'}).status_code == 403
        assert c.get('/api/demo', headers={'Sec-Fetch-Site':'cross-site'}).status_code == 403
        assert c.get('/api/demo', headers={'Origin':'http://testserver'}).status_code == 200
        assert c.get('/api/jobs/missing').status_code == 404
        assert c.get('/api/demo', headers={'Host':'foreign.example'}).status_code == 400
        assert 'frame-ancestors' in c.get('/').headers['Content-Security-Policy']


def test_source_import_only_explicit_path(tmp_path, monkeypatch):
    from sp5generator import sp5_adapter
    from sp5generator.demo import make_demo
    seen=[]
    monkeypatch.setattr(sp5_adapter,'inspect_directory',lambda directory: {'groups':[{'id':'t1','name':'Team A'}], 'directory':directory})
    def importer(**kwargs):
        seen.append(kwargs)
        s=make_demo()
        s.metadata['history_matrix']=[{'employee_id':s.employees[0].id,'suggested_approvals':[]}]
        return s
    monkeypatch.setattr(sp5_adapter,'import_directory',importer)
    with TestClient(create_app(str(tmp_path),start_worker=False)) as c:
        assert c.get('/api/source',params={'directory':'synthetic'}).json()['groups'][0]['name']=='Team A'
        response=c.post('/api/import',json={'directory':'synthetic','period_start':'2026-01-05','period_end':'2026-01-18','team_id':'t1','timezone':'UTC'})
        assert response.status_code==200
        assert response.json()['matrix_suggestions']
        assert seen[0]['directory']=='synthetic'


def test_remote_source_and_import_stay_server_configured(tmp_path, monkeypatch):
    from sp5generator import api_adapter
    from sp5generator.demo import make_demo
    seen = []
    monkeypatch.setattr(api_adapter, 'inspect_api', lambda: {'groups': [{'id': '1', 'name': 'Team A'}]})
    def importer(**kwargs):
        seen.append(kwargs)
        return make_demo()
    monkeypatch.setattr(api_adapter, 'import_api', importer)
    with TestClient(create_app(str(tmp_path), start_worker=False)) as c:
        assert c.get('/api/remote-source').json()['groups'][0]['id'] == '1'
        response = c.post('/api/remote-import', json={'period_start': '2026-01-05', 'period_end': '2026-01-18', 'team_id': '1', 'timezone': 'UTC'})
        assert response.status_code == 200
        assert seen[0]['history_plan'] == 'ist'
        assert 'directory' not in seen[0]


def test_health_and_invalid_input_do_not_echo_submitted_values(tmp_path):
    with TestClient(create_app(str(tmp_path), start_worker=False)) as c:
        assert c.get('/healthz').json() == {'status': 'ok'}
        response = c.post('/api/jobs', json={'snapshot_id': 'synthetic', 'time_limit': 'synthetic-invalid-marker'})
        assert response.status_code == 422
        assert 'synthetic-invalid-marker' not in response.text
        assert response.json()['fields'][0]['location'] == ['body', 'time_limit']


def test_request_body_limit_covers_chunked_input():
    import asyncio
    from sp5generator.request_limits import RequestSizeLimit
    called = []
    async def inner(scope, receive, send):
        called.append(True)
    async def run():
        sent = []
        chunks = iter([{'type': 'http.request', 'body': b'123', 'more_body': True},
                       {'type': 'http.request', 'body': b'456', 'more_body': False}])
        async def receive():
            return next(chunks)
        async def send(message):
            sent.append(message)
        await RequestSizeLimit(inner, limit=5)({'type': 'http', 'method': 'POST'}, receive, send)
        assert sent[0]['status'] == 413
        assert not called
    asyncio.run(run())


def test_integrated_login_respects_browser_boundary(tmp_path, monkeypatch):
    password_file = tmp_path / 'password'
    password_file.write_text('synthetic-login-only')
    monkeypatch.setenv('SP5_WEB_PASSWORD_FILE', str(password_file))
    with TestClient(create_app(str(tmp_path / 'state'), start_worker=False)) as c:
        assert c.get('/healthz').status_code == 200
        assert c.get('/api/demo').status_code == 401
        assert c.get('/').url.path == '/login'
        assert c.post('/login', data={'password': 'synthetic-login-only'}, headers={'Origin': 'http://other.invalid'}).status_code == 403
        response = c.post('/login', data={'password': 'synthetic-login-only'}, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers['Cache-Control'] == 'no-store'
        assert c.get('/api/version').json()['auth_enabled']
        assert c.get('/api/demo').status_code == 200
        c.post('/logout')
        assert c.get('/api/demo').status_code == 401


def test_project_check_does_not_change_saved_revision(tmp_path):
    with TestClient(create_app(str(tmp_path), start_worker=False)) as c:
        snapshot = c.put('/api/snapshots', json=c.get('/api/demo').json()).json()
        imported = dict(snapshot, revision='portable-copy')
        checked = c.post('/api/snapshots/check', json=imported)
        assert checked.status_code == 200
        assert checked.json()['revision'] == 'portable-copy'
        invalid = c.post('/api/snapshots/check', json={'id': snapshot['id']})
        assert invalid.status_code == 422
        assert c.get('/api/snapshots/' + snapshot['id']).json() == snapshot


def test_job_history_recovers_exact_input_and_rejects_stale_submission(tmp_path):
    with TestClient(create_app(str(tmp_path), start_worker=False)) as c:
        snapshot = c.put('/api/snapshots', json=c.get('/api/demo').json()).json()
        job = c.post('/api/jobs', json={'snapshot_id': snapshot['id'],
                     'snapshot_revision': snapshot['revision'], 'time_limit': 1}).json()
        changed = dict(snapshot)
        changed['metadata'] = {**snapshot['metadata'], 'project_note': 'Synthetic revision'}
        current = c.put('/api/snapshots', json=changed).json()
        assert current['revision'] != snapshot['revision']
        assert c.get('/api/jobs/' + job['id'] + '/snapshot').json() == snapshot
        assert c.post('/api/jobs', json={'snapshot_id': snapshot['id'],
                      'snapshot_revision': snapshot['revision']}).status_code == 409
        history = c.get('/api/jobs', params={'snapshot_id': snapshot['id']}).json()
        assert len(history) == 1 and history[0]['id'] == job['id']
        assert 'payload' not in history[0] and 'owner' not in history[0]
        assert c.get('/api/jobs', params={'snapshot_id': 'missing'}).json() == []
        assert c.get('/api/jobs', params={'limit': 101}).status_code == 422
        assert c.get('/api/jobs/missing/snapshot').status_code == 404
        assert c.get('/api/snapshots').json()[0]['period_start'] == snapshot['period_start']


def test_json_export_reports_recomputed_vacancies(tmp_path):
    with TestClient(create_app(str(tmp_path), start_worker=False)) as c:
        snapshot = c.get('/api/demo').json()
        response = c.post('/api/export/json', json={
            'snapshot': snapshot, 'assignments': snapshot['assignments'],
        })
        assert response.status_code == 200
        result = response.json()
        assert result['validation']['valid'] and not result['validation']['complete']
        assert sum(result['vacancies'].values()) > 0
        assert result['solver_status'] == 'UNKNOWN'


@pytest.mark.parametrize('case', ['timezone', 'period', 'segments'])
def test_unsafe_project_structure_does_not_replace_saved_work(tmp_path, case):
    with TestClient(create_app(str(tmp_path), start_worker=False)) as c:
        snapshot = c.put('/api/snapshots', json=c.get('/api/demo').json()).json()
        import copy
        invalid = copy.deepcopy(snapshot)
        if case == 'timezone':
            invalid['timezone'] = 'Missing/SyntheticZone'
        elif case == 'period':
            invalid['period_end'] = '2025-01-01'
        else:
            invalid['shifts'][0]['segments'] = []
        assert c.post('/api/snapshots/check', json=invalid).status_code == 422
        assert c.put('/api/snapshots', json=invalid).status_code == 422
        assert c.get('/api/snapshots/' + snapshot['id']).json() == snapshot


def test_unconfirmed_rules_remain_editable_projects(tmp_path):
    with TestClient(create_app(str(tmp_path), start_worker=False)) as c:
        snapshot = c.get('/api/demo').json()
        snapshot['profiles'][0]['confirmed'] = False
        snapshot['unresolved'] = ['Synthetic source rule requires confirmation']
        assert c.post('/api/snapshots/check', json=snapshot).status_code == 200
        assert c.put('/api/snapshots', json=snapshot).status_code == 200
