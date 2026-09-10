"""Local single-user web application with a separate persistent solver worker."""
import argparse
import asyncio
from contextlib import asynccontextmanager
from datetime import date
import multiprocessing
import os
from pathlib import Path
import tempfile
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field

from .jobs import Store, Conflict, run_worker
from .models import Snapshot, Assignment, Result


class ImportRequest(BaseModel):
    directory: str
    period_start: date
    period_end: date
    team_id: str
    timezone: str
    history_plan: Literal['ist', 'soll', 'both'] = 'ist'
    history_start: date | None = None
    history_end: date | None = None


class JobRequest(BaseModel):
    snapshot_id: str
    time_limit: float = Field(default=30, gt=0, le=600)
    partial: bool = False


class PlanRequest(BaseModel):
    snapshot: Snapshot
    assignments: list[Assignment]


def create_app(state_dir: str = './generator-state', start_worker: bool = True):
    store = Store(Path(state_dir) / 'planning.sqlite3')
    owner = 'local-user'

    @asynccontextmanager
    async def lifespan(app):
        worker = None
        if start_worker:
            worker = multiprocessing.get_context('spawn').Process(target=run_worker, args=(store.path,))
            worker.start()
            await asyncio.sleep(0.2)
            if not worker.is_alive():
                worker.join()
                raise RuntimeError('Solver worker could not start; check state directory and existing worker')
        app.state.worker = worker
        try:
            yield
        finally:
            if worker:
                worker.terminate()
                worker.join(8)
                if worker.is_alive():
                    worker.kill()
                    worker.join()

    app = FastAPI(title='OpenSchichtplaner5 Generator', lifespan=lifespan)
    app.state.store = store
    allowed_hosts = ['localhost', '127.0.0.1', '[::1]']
    if not start_worker:
        allowed_hosts.append('testserver')
    allowed_hosts.extend(h.strip() for h in os.environ.get('SP5_WEB_ALLOWED_HOSTS', '').split(',') if h.strip())
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    @app.middleware('http')
    async def local_browser_boundary(request: Request, call_next):
        # No CORS: a foreign website must not trigger local directory access or jobs.
        origin = request.headers.get('origin')
        if origin and origin != str(request.base_url).rstrip('/'):
            return JSONResponse({'detail': 'Cross-origin requests are not permitted'}, status_code=403)
        if request.headers.get('sec-fetch-site') == 'cross-site':
            return JSONResponse({'detail': 'Cross-site requests are not permitted'}, status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        return response

    @app.exception_handler(Conflict)
    async def conflict(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=409)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({'detail': 'Not found'}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=422)

    @app.get('/api/demo')
    def demo():
        from .demo import make_demo
        from uuid import uuid4
        snapshot = make_demo()
        snapshot.id = str(uuid4())
        return snapshot

    @app.get('/api/source')
    def source(directory: str):
        from .sp5_adapter import inspect_directory
        try:
            return inspect_directory(directory)
        except (OSError, ImportError) as exc:
            raise HTTPException(400, 'Verzeichnis nicht lesbar oder SP5-Erweiterung nicht installiert') from exc

    @app.post('/api/import')
    def import_source(data: ImportRequest):
        from .sp5_adapter import import_directory
        try:
            snapshot = import_directory(**data.model_dump())
        except (OSError, ImportError) as exc:
            raise HTTPException(400, 'Import nicht möglich: Verzeichnis und SP5-Erweiterung prüfen') from exc
        return {'snapshot': snapshot, 'matrix_suggestions': snapshot.metadata.get('history_matrix', [])}

    @app.put('/api/snapshots')
    def save(snapshot: Snapshot):
        return store.save_snapshot(snapshot, owner)

    @app.get('/api/snapshots')
    def list_snapshots():
        with store.connect() as conn:
            rows = conn.execute('SELECT id,revision FROM snapshots WHERE owner=? ORDER BY rowid DESC', (owner,)).fetchall()
        return [dict(row) for row in rows]

    @app.get('/api/snapshots/{id}')
    def get_snapshot(id: str):
        return store.get_snapshot(id, owner)

    @app.post('/api/jobs')
    def submit(data: JobRequest):
        worker = getattr(app.state, 'worker', None)
        if start_worker and (worker is None or not worker.is_alive()):
            raise HTTPException(503, 'Berechnungsprozess nicht verfügbar; Anwendung neu starten')
        return store.submit(data.snapshot_id, owner, data.time_limit, data.partial)

    @app.get('/api/jobs/{id}')
    def get_job(id: str):
        return store.get_job(id, owner)

    @app.post('/api/jobs/{id}/cancel')
    def cancel(id: str):
        return store.cancel(id, owner)

    @app.post('/api/validate')
    def validate_plan(data: PlanRequest):
        from .validator import validate
        return validate(data.snapshot, data.assignments)

    @app.post('/api/export/{format}')
    def export_plan(format: str, data: PlanRequest):
        from .domain import snapshot_hash
        from .validator import validate
        from .export import export_table
        validation = validate(data.snapshot, data.assignments)
        if not validation.valid:
            raise HTTPException(422, 'Ungültigen Entwurf zuerst korrigieren')
        result = Result(snapshot_id=data.snapshot.id, snapshot_hash=snapshot_hash(data.snapshot), solver_status='UNKNOWN', assignments=data.assignments, validation=validation, runtime_seconds=0, parameters={'origin': 'edited-draft', 'solver_status_available': False})
        if format == 'json':
            return Response(result.model_dump_json(indent=2), media_type='application/json', headers={'Content-Disposition': 'attachment; filename="plan.json"'})
        if format not in ('csv', 'xlsx'):
            raise HTTPException(404, 'Unknown format')
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / ('plan.' + format)
            export_table(data.snapshot, result, path)
            content = path.read_bytes()
        return Response(content, media_type='text/csv' if format == 'csv' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition': f'attachment; filename="plan.{format}"'})

    static = Path(__file__).with_name('static')
    app.mount('/static', StaticFiles(directory=static), name='static')

    @app.get('/')
    def index():
        return FileResponse(static / 'index.html')

    return app


def main():
    parser = argparse.ArgumentParser(description='OpenSchichtplaner5 Generator – lokale Weboberfläche')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--state-dir', default='./generator-state')
    args = parser.parse_args()
    import uvicorn
    uvicorn.run(create_app(args.state_dir), host=args.host, port=args.port, access_log=False)


if __name__ == '__main__':
    main()
