"""Synthetic route tests for local browser planning and persisted edits."""
import pytest
pytest.importorskip('fastapi')
from fastapi.testclient import TestClient
from sp5generator.webapp import create_app
from sp5generator.solver import solve


@pytest.mark.parametrize("text", ["private-name\x01", "x" * 32768],
                         ids=["control", "overlong"])
def test_xlsx_text_error_is_actionable_without_echoing_source(tmp_path, text):
    from sp5generator.demo import make_demo

    snapshot = make_demo(days=1)
    snapshot.assignments = []
    snapshot.employees[0].name = text
    original = snapshot.model_dump(mode="json")
    payload = {"snapshot": original, "assignments": []}
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        response = client.post('/api/export/xlsx', json=payload)
        assert response.status_code == 422
        assert 'Excel-Export' in response.json()['detail']
        assert text not in response.text
        assert client.post('/api/export/csv', json=payload).status_code == 200


def test_local_web_persist_solve_and_export(tmp_path):
    with TestClient(create_app(str(tmp_path), start_worker=False)) as c:
        assert c.get('/').status_code == 200
        from sp5generator import __version__
        assert c.get('/api/version').json() == {'version': __version__, 'auth_enabled': False}
        assert 'OpenSchichtplaner5 Generator' in c.get('/').text
        assert c.get('/static/app.js').status_code == 200
        assert c.get('/static/app.js').headers['Cache-Control'] == 'public, max-age=0, must-revalidate'
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
        assert seen[0]['reference_plan'] == 'ist'
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


@pytest.mark.parametrize('report', [
    {}, [], 'broken',
    {'newPeople': 'person', 'newServices': [], 'review': [], 'reusedPeople': 0, 'classified': 0},
    {'newPeople': [], 'newServices': [], 'review': [None], 'reusedPeople': 0, 'classified': 0},
    {'newPeople': [], 'newServices': [], 'review': [], 'reusedPeople': -1, 'classified': 0},
])
def test_invalid_setup_review_is_rejected_before_replacing_a_project(tmp_path, report):
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        saved = client.put('/api/snapshots', json=client.get('/api/demo').json()).json()
        imported = {**saved, 'metadata': {**saved['metadata'], 'setup_review': report}}
        for method, url in [('post', '/api/snapshots/check'), ('put', '/api/snapshots')]:
            rejected = getattr(client, method)(url, json=imported)
            assert rejected.status_code == 422
            assert 'setup_review' in rejected.json()['detail']
        assert client.get('/api/snapshots/' + saved['id']).json() == saved


@pytest.mark.parametrize('key,value', [
    ('history_matrix', {}), ('history_matrix', [None]),
    ('history_matrix', [{'employee_id': 'synthetic', 'suggested_approvals': {}}]),
    ('history_matrix', [{'employee_id': 'synthetic', 'observed_shifts': [None]}]),
    ('history_matrix', [{'employee_id': 'synthetic', 'suggested_approvals': [None]}]),
    ('history_automation', {}), ('history_automation', {'minimum_days': 3, 'applied': {}}),
    ('history_automation', {'minimum_days': 3, 'applied': [None]}),
])
def test_invalid_history_metadata_does_not_replace_project(tmp_path, key, value):
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        saved = client.put('/api/snapshots', json=client.get('/api/demo').json()).json()
        imported = {**saved, 'metadata': {**saved['metadata'], key: value}}
        for method, url in [('post', '/api/snapshots/check'), ('put', '/api/snapshots')]:
            rejected = getattr(client, method)(url, json=imported)
            assert rejected.status_code == 422
            assert key in rejected.json()['detail']
        assert client.get('/api/snapshots/' + saved['id']).json() == saved


def test_valid_setup_review_and_custom_metadata_are_preserved(tmp_path):
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        snapshot = client.get('/api/demo').json()
        snapshot['metadata'].update({
            'custom_note': {'version': 1},
            'history_matrix': [{'employee_id': 'synthetic-person', 'future_field': True}],
            'history_automation': {'minimum_days': 3, 'applied': [], 'future_field': True},
            'setup_review': {'newPeople': ['synthetic-person'], 'newServices': [],
                             'review': ['Synthetic review'], 'reusedPeople': 0,
                             'classified': 1, 'future_field': {'keep': True}},
        })
        checked = client.post('/api/snapshots/check', json=snapshot)
        assert checked.status_code == 200
        assert checked.json()['metadata'] == snapshot['metadata']


@pytest.mark.parametrize('key', ['workplaces', 'group_tree', 'services'])
@pytest.mark.parametrize('value', [{}, [None], ['broken']])
def test_invalid_display_catalog_is_rejected_without_replacing_project(tmp_path, key, value):
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        saved = client.put('/api/snapshots', json=client.get('/api/demo').json()).json()
        imported = {**saved, 'metadata': {**saved['metadata'], key: value}}
        for method, url in [('post', '/api/snapshots/check'), ('put', '/api/snapshots')]:
            rejected = getattr(client, method)(url, json=imported)
            assert rejected.status_code == 422
            assert key in rejected.json()['detail']
        assert client.get('/api/snapshots/' + saved['id']).json() == saved


def test_optional_and_legacy_display_catalogs_are_preserved(tmp_path):
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        snapshot = client.get('/api/demo').json()
        for metadata in [
            dict.fromkeys(['workplaces', 'group_tree', 'services', 'history_matrix', 'history_automation']),
            {'workplaces': [{'id': 'synthetic', 'name': None, 'future': True}],
             'group_tree': [{'id': 1, 'name': 'Synthetic'}],
             'services': [{'id': 1, 'name': 'Synthetic legacy'}, {'function_id': 'synthetic-service'}]},
        ]:
            snapshot['metadata'].update(metadata)
            checked = client.post('/api/snapshots/check', json=snapshot)
            assert checked.status_code == 200
            assert checked.json()['metadata'] == snapshot['metadata']


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


def test_remote_import_rejects_unsavable_structure_at_import(tmp_path, monkeypatch):
    from sp5generator.demo import make_demo
    snapshot = make_demo()
    snapshot.employees[0].availability *= 26000
    monkeypatch.setattr('sp5generator.api_adapter.import_api', lambda **kwargs: snapshot)
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        result = client.post('/api/remote-import', json={
            'period_start': '2026-01-01', 'period_end': '2026-01-31',
            'timezone': 'UTC', 'team_ids': ['1'],
        })
        assert result.status_code == 422
        assert 'size_limit' in result.json()['detail']
        assert 'Zu viele verschachtelte Planungsdatensätze' in result.json()['detail']
        assert client.get('/api/snapshots').json() == []


def test_history_automation_requires_explicit_import_option(tmp_path, monkeypatch):
    from sp5generator.demo import make_demo
    def imported(**kwargs):
        snapshot = make_demo()
        person = snapshot.employees[0]
        person.approvals = []
        snapshot.metadata['history_matrix'] = [{'employee_id': person.id, 'suggested_approvals': [
            {'function_id': 'synthetic-service', 'evidence_days': 3}]}]
        return snapshot
    monkeypatch.setattr('sp5generator.api_adapter.import_api', imported)
    payload = {'period_start': '2026-01-01', 'period_end': '2026-01-31', 'timezone': 'UTC', 'team_ids': ['1']}
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        default = client.post('/api/remote-import', json=payload).json()['snapshot']
        assert default['employees'][0]['approvals'] == []
        enabled = client.post('/api/remote-import', json={**payload, 'auto_history': True}).json()['snapshot']
        assert enabled['employees'][0]['approvals'][0]['function_id'] == 'synthetic-service'
        assert enabled['metadata']['history_automation']['minimum_days'] == 3


def test_readiness_uses_solver_input_checks_without_saving(tmp_path):
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        snapshot = client.get('/api/demo').json()
        snapshot['unresolved'] = ['Synthetic configuration is incomplete']
        report = client.post('/api/readiness', json=snapshot)
        assert report.status_code == 200
        assert report.json()['ready'] is False
        assert any(d['code'] == 'unresolved' for d in report.json()['diagnostics'])
        assert client.get('/api/snapshots').json() == []


def test_readiness_explains_empty_additional_qualification_gate(tmp_path):
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        snapshot = client.get('/api/demo').json()
        position = snapshot['positions'][0]
        position['qualifications_required'] = True
        position['qualification_ids'] = []
        report = client.post('/api/readiness', json=snapshot).json()
        assert not report['ready']
        assert any(d['code'] == 'qualification' and position['name'] in d['message']
                   and 'deaktivieren' in d['message'] for d in report['diagnostics'])
        position['qualifications_required'] = False
        report = client.post('/api/readiness', json=snapshot).json()
        assert not any(d['code'] == 'qualification' for d in report['diagnostics'])
        assert client.get('/api/snapshots').json() == []


def test_readiness_ignores_unused_qualification_gate_until_position_is_demanded(tmp_path):
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        snapshot = client.get('/api/demo').json()
        unused = {**snapshot['positions'][0], 'id': 'unused-position',
                  'name': 'Unbenutzte Testfunktion', 'qualifications_required': True,
                  'qualification_ids': []}
        snapshot['positions'].append(unused)
        report = client.post('/api/readiness', json=snapshot).json()
        assert report['ready']
        assert not any(d['code'] == 'qualification' for d in report['diagnostics'])

        snapshot['demands'][0]['position_id'] = unused['id']
        report = client.post('/api/readiness', json=snapshot).json()
        assert not report['ready']
        assert any(d['code'] == 'qualification' and unused['name'] in d['message']
                   for d in report['diagnostics'])
        assert snapshot['positions'][-1]['qualifications_required'] is True
        assert client.get('/api/snapshots').json() == []


def test_readiness_person_diagnostics_keep_identity_with_duplicate_names(tmp_path):
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        snapshot = client.get('/api/demo').json()
        first, second = snapshot['employees'][:2]
        first['name'] = second['name'] = 'Synthetischer gleicher Name'
        first['profile_ids'] = []
        report = client.post('/api/readiness', json=snapshot)
        assert report.status_code == 200
        issues = [d for d in report.json()['diagnostics'] if d['code'] == 'profile']
        assert issues
        assert all(d['employee_id'] == first['id'] for d in issues)
        assert all(second['id'] != d['employee_id'] for d in issues)
        assert client.get('/api/snapshots').json() == []


@pytest.mark.parametrize('endpoint,module', [('/api/import', 'sp5_adapter'), ('/api/remote-import', 'api_adapter')])
def test_reference_selection_request_validates_and_passes_independently(tmp_path, monkeypatch, endpoint, module):
    from sp5generator.demo import make_demo
    import importlib
    adapter = importlib.import_module('sp5generator.' + module)
    seen = []
    def importer(**kwargs):
        seen.append(kwargs)
        return make_demo()
    monkeypatch.setattr(adapter, 'import_directory' if module == 'sp5_adapter' else 'import_api', importer)
    payload = {'period_start': '2026-01-05', 'period_end': '2026-01-18', 'team_id': '1', 'timezone': 'UTC',
               'history_plan': 'both', 'reference_plan': 'soll'}
    if module == 'sp5_adapter':
        payload['directory'] = 'synthetic'
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        assert client.post(endpoint, json=payload).status_code == 200
        assert seen[0]['reference_plan'] == 'soll' and seen[0]['history_plan'] == 'both'
        assert seen[0]['existing_plan_mode'] == 'reference'
        assert client.post(endpoint, json={**payload, 'reference_plan': 'both'}).status_code == 422
        assert len(seen) == 1


@pytest.mark.parametrize('endpoint,module', [('/api/import', 'sp5_adapter'), ('/api/remote-import', 'api_adapter')])
def test_demand_source_request_validates_and_passes(tmp_path, monkeypatch, endpoint, module):
    from sp5generator.demo import make_demo
    from types import SimpleNamespace
    import importlib
    adapter = importlib.import_module('sp5generator.' + module)
    seen = []
    def importer(*args, **kwargs):
        seen.append(kwargs)
        return make_demo()
    monkeypatch.setattr(adapter, 'import_snapshot', importer)
    monkeypatch.setattr(adapter, 'historical_matrix', lambda *args: [])
    db = SimpleNamespace(get_groups=lambda: [{'ID': 1}], get_group_members=lambda group_id: [],
                         get_employees=lambda: [])
    payload = {'period_start': '2026-01-05', 'period_end': '2026-01-18', 'team_id': '1', 'timezone': 'UTC'}
    if module == 'sp5_adapter':
        payload['directory'] = 'synthetic'
        monkeypatch.setattr(adapter, '_source_database', lambda directory: (db, {}))
    else:
        monkeypatch.setattr(adapter, 'APIClient', lambda: SimpleNamespace(authorize=lambda: None,
                                                                         verify=lambda: 'synthetic'))
        monkeypatch.setattr(adapter, '_Database', lambda *args: db)
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        assert client.post(endpoint, json=payload).status_code == 200
        assert seen[0]['demand_source'] == 'requirements'
        assert client.post(endpoint, json={**payload, 'demand_source': 'observed'}).status_code == 200
        assert seen[1]['demand_source'] == 'observed'
        assert client.post(endpoint, json={**payload, 'demand_source': 'invalid'}).status_code == 422
        assert len(seen) == 2
