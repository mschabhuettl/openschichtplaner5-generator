"""Synthetic route tests for local browser planning and persisted edits."""
import pytest
pytest.importorskip('fastapi')
from fastapi.testclient import TestClient
from sp5generator.webapp import create_app
from sp5generator.solver import solve


def test_local_web_persist_solve_and_export(tmp_path):
    with TestClient(create_app(str(tmp_path), start_worker=False)) as c:
        assert c.get('/').status_code == 200
        assert 'OpenSchichtplaner5 Generator' in c.get('/').text
        assert c.get('/static/app.js').status_code == 200
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
