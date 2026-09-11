"""Local single-user web application with a separate persistent solver worker."""
import argparse
import asyncio
from contextlib import asynccontextmanager
from datetime import date, datetime
import multiprocessing
import os
from pathlib import Path
import tempfile
from typing import Literal
from zoneinfo import ZoneInfoNotFoundError

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field

from .jobs import Store, Conflict, run_worker
from .models import Snapshot, Assignment, Result


class ApiImportRequest(BaseModel):
    period_start: date
    period_end: date
    team_id: str | None = None
    team_ids: list[str] | None = None
    timezone: str
    history_plan: Literal['ist', 'soll', 'both'] = 'ist'
    auto_history: bool = False
    history_min_days: int = Field(default=3, ge=2, le=1097)
    existing_plan_mode: Literal['reference', 'fixed'] = 'reference'
    history_start: date | None = None
    history_end: date | None = None


class ImportRequest(ApiImportRequest):
    directory: str


class JobRequest(BaseModel):
    snapshot_id: str
    snapshot_revision: str | None = None
    time_limit: float = Field(default=30, gt=0, le=600)
    partial: bool = False


class PlanRequest(BaseModel):
    snapshot: Snapshot
    assignments: list[Assignment] = Field(max_length=5000)


class ProjectRevisionRequest(BaseModel):
    model_config = {'str_strip_whitespace': True}
    revision: str = Field(min_length=1, max_length=80)


class ProjectCopyRequest(ProjectRevisionRequest):
    project_name: str | None = Field(default=None, min_length=1, max_length=120)


class LocalIntervalRequest(BaseModel):
    timezone: str = Field(min_length=1, max_length=100)
    start: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$')
    end: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$')


def check_project_structure(snapshot: Snapshot):
    """Reject unsafe display/input boundaries while allowing unfinished rules."""
    from .domain import input_diagnostics
    blocking_codes = {'input', 'date_range', 'period', 'interval', 'size_limit', 'numeric_range'}
    codes = sorted({item.code for item in input_diagnostics(snapshot)
                    if item.code in blocking_codes})
    if codes:
        raise HTTPException(422, 'Projektstruktur ungültig: ' + ', '.join(codes))
    return snapshot


def create_app(state_dir: str = './generator-state', start_worker: bool = True):
    store = Store(Path(state_dir) / 'planning.sqlite3')
    owner = 'local-user'

    @asynccontextmanager
    async def lifespan(app):
        worker = None
        try:
            if start_worker:
                context = multiprocessing.get_context('spawn')
                ready = context.Event()
                worker = context.Process(target=run_worker, args=(store.path,), kwargs={'ready': ready})
                worker.start()
                # Importing the solver in a spawned process and acquiring its
                # exclusive store lock must finish before the web service is ready.
                deadline = asyncio.get_running_loop().time() + 15
                while not ready.is_set():
                    if not worker.is_alive() or asyncio.get_running_loop().time() >= deadline:
                        raise RuntimeError('Solver worker could not start; check state directory and existing worker')
                    await asyncio.sleep(0.05)
                if not worker.is_alive():
                    raise RuntimeError('Solver worker stopped during startup')
            app.state.worker = worker
            yield
        finally:
            if worker and worker.pid is not None:
                if worker.is_alive():
                    worker.terminate()
                worker.join(12)
                if worker.is_alive():
                    worker.kill()
                    worker.join(5)
                worker.close()
            app.state.worker = None

    app = FastAPI(title='OpenSchichtplaner5 Generator', lifespan=lifespan)
    app.state.store = store
    from .web_auth import install_web_auth
    install_web_auth(app)
    from .request_limits import RequestSizeLimit
    app.add_middleware(RequestSizeLimit)
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
        if request.method in {'POST', 'PUT', 'PATCH'}:
            try:
                content_length = int(request.headers.get('content-length', '0'))
            except ValueError:
                return JSONResponse({'detail': 'Invalid Content-Length'}, status_code=400)
            if content_length > 16 * 1024 * 1024:
                return JSONResponse({'detail': 'Request exceeds 16 MiB limit'}, status_code=413)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        if request.url.path.startswith('/static/') and response.status_code in {200, 304}:
            # Public code/assets contain no project data. Revalidate their ETag
            # on every navigation so an upgrade cannot leave stale JS or CSS.
            response.headers['Cache-Control'] = 'public, max-age=0, must-revalidate'
            if response.headers.get('etag', '').startswith('"'):
                response.headers['ETag'] = 'W/' + response.headers['etag']
            response.headers.add_vary_header('Accept-Encoding')
        else:
            response.headers['Cache-Control'] = 'no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return JSONResponse({'detail': 'Ungültige Eingabe. Feldtypen und Pflichtangaben anhand des Eingabeschemas prüfen.', 'fields': [{'location': list(e['loc']), 'type': e['type']} for e in exc.errors()]}, status_code=422)

    @app.exception_handler(Conflict)
    async def conflict(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=409)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({'detail': 'Not found'}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=422)

    @app.get('/healthz')
    def health():
        worker = getattr(app.state, 'worker', None)
        healthy = not start_worker or (worker is not None and worker.is_alive())
        try:
            with store.connect() as connection:
                connection.execute('SELECT 1').fetchone()
        except Exception:
            healthy = False
        return JSONResponse({'status': 'ok' if healthy else 'unavailable'}, status_code=200 if healthy else 503)

    @app.get('/api/version')
    def version():
        from . import __version__
        return {'version': __version__, 'auth_enabled': app.state.web_auth_enabled}

    @app.get('/api/status')
    def service_status():
        from . import __version__
        worker = getattr(app.state, 'worker', None)
        ready = not start_worker or (worker is not None and worker.is_alive())
        counts = {}
        storage_ready = True
        try:
            with store.connect() as connection:
                counts = {row['state']: row['count'] for row in connection.execute(
                    "SELECT state,count(*) AS count FROM jobs WHERE owner=? AND state IN ('queued','running') GROUP BY state",
                    (owner,),
                )}
        except Exception:
            storage_ready = False
        return JSONResponse({
            'version': __version__,
            'status': 'ok' if ready and storage_ready else 'unavailable',
            'worker': {'enabled': start_worker, 'ready': ready},
            'storage_ready': storage_ready,
            'jobs': {'queued': counts.get('queued', 0), 'running': counts.get('running', 0)},
        }, status_code=200 if ready and storage_ready else 503)

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
            snapshot = import_directory(**data.model_dump(exclude={"auto_history", "history_min_days"}))
        except (OSError, ImportError) as exc:
            raise HTTPException(400, 'Import nicht möglich: Verzeichnis und SP5-Erweiterung prüfen') from exc
        if data.auto_history:
            from .history_approvals import apply_history_approvals
            apply_history_approvals(snapshot, data.history_min_days)
        return {'snapshot': check_project_structure(snapshot), 'matrix_suggestions': snapshot.metadata.get('history_matrix', [])}

    @app.get('/api/remote-source')
    def remote_source():
        from .api_adapter import inspect_api
        return inspect_api()

    @app.post('/api/remote-import')
    def remote_import(data: ApiImportRequest):
        from .api_adapter import import_api
        snapshot = import_api(**data.model_dump(exclude={"auto_history", "history_min_days"}))
        if data.auto_history:
            from .history_approvals import apply_history_approvals
            apply_history_approvals(snapshot, data.history_min_days)
        return {'snapshot': check_project_structure(snapshot), 'matrix_suggestions': snapshot.metadata.get('history_matrix', [])}

    @app.post('/api/snapshots/check')
    def check_snapshot(snapshot: Snapshot):
        """Normalize an imported project without replacing a persisted revision."""
        return check_project_structure(snapshot)

    from .project_creation import ProjectCreateRequest, create_project

    @app.post('/api/projects/new')
    def new_project(data: ProjectCreateRequest):
        return {'snapshot': check_project_structure(create_project(data))}

    @app.post('/api/intervals/resolve')
    def resolve_interval(data: LocalIntervalRequest):
        from .timeutils import localize, minute
        try:
            start_local = datetime.fromisoformat(data.start)
            end_local = datetime.fromisoformat(data.end)
            start = localize(start_local.date(), start_local.strftime('%H:%M'), data.timezone)
            end = localize(end_local.date(), end_local.strftime('%H:%M'), data.timezone)
        except ZoneInfoNotFoundError as exc:
            raise HTTPException(422, 'Unbekannte Projektzeitzone') from exc
        except (ValueError, OverflowError) as exc:
            message = str(exc)
            if message.startswith('Mehrdeutige'):
                message = 'Diese Uhrzeit kommt bei der Zeitumstellung zweimal vor. Beginn oder Ende außerhalb dieser doppelten Stunde wählen.'
            elif message.startswith('Nicht existierende'):
                message = 'Diese Uhrzeit existiert wegen der Zeitumstellung nicht. Eine Uhrzeit vor oder nach dem Zeitsprung wählen.'
            else:
                message = 'Datum, Uhrzeit oder Projektzeitzone ungültig.'
            raise HTTPException(422, message) from exc
        if minute(end) <= minute(start):
            raise HTTPException(422, 'Das Ende muss nach dem Beginn liegen.')
        return {'start': start.isoformat(), 'end': end.isoformat()}

    @app.put('/api/snapshots')
    def save(snapshot: Snapshot):
        return store.save_snapshot(check_project_structure(snapshot), owner)

    @app.get('/api/snapshots')
    def list_snapshots(archived: bool = False,
                       limit: int = Query(default=200, ge=1, le=1000),
                       offset: int = Query(default=0, ge=0, le=1_000_000)):
        return store.list_snapshots(owner, archived=archived, limit=limit, offset=offset)

    @app.post('/api/snapshots/{id}/copy')
    def copy_snapshot(id: str, data: ProjectCopyRequest):
        return store.copy_snapshot(id, owner, data.revision, data.project_name)

    @app.post('/api/snapshots/{id}/archive')
    def archive_snapshot(id: str, data: ProjectRevisionRequest):
        return store.set_archived(id, owner, data.revision, True)

    @app.post('/api/snapshots/{id}/restore')
    def restore_snapshot(id: str, data: ProjectRevisionRequest):
        return store.set_archived(id, owner, data.revision, False)

    @app.get('/api/snapshots/{id}')
    def get_snapshot(id: str):
        return store.get_snapshot(id, owner)

    @app.post('/api/jobs')
    def submit(data: JobRequest):
        worker = getattr(app.state, 'worker', None)
        if start_worker and (worker is None or not worker.is_alive()):
            raise HTTPException(503, 'Berechnungsprozess nicht verfügbar; Anwendung neu starten')
        return store.submit(data.snapshot_id, owner, data.time_limit, data.partial,
                            revision=data.snapshot_revision)

    @app.get('/api/jobs')
    def list_jobs(snapshot_id: str | None = None, limit: int = Query(default=50, ge=1, le=100)):
        return store.list_jobs(owner, snapshot_id=snapshot_id, limit=limit)

    @app.get('/api/jobs/{id}/snapshot')
    def get_job_snapshot(id: str):
        return store.get_job_snapshot(id, owner)

    @app.get('/api/jobs/{id}/status')
    def get_job_status(id: str):
        return store.get_job_status(id, owner)

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
        from .export import export_table, vacancy_counts
        validation = validate(data.snapshot, data.assignments)
        if not validation.valid:
            raise HTTPException(422, 'Ungültigen Entwurf zuerst korrigieren')
        result = Result(snapshot_id=data.snapshot.id, snapshot_hash=snapshot_hash(data.snapshot), solver_status='UNKNOWN', assignments=data.assignments, vacancies=vacancy_counts(data.snapshot, data.assignments), validation=validation, runtime_seconds=0, parameters={'origin': 'edited-draft', 'solver_status_available': False})
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
    # Compress deterministic assets only. Personnel responses and authenticated
    # forms remain uncompressed and are never retained in browser caches.
    app.mount('/static', GZipMiddleware(StaticFiles(directory=static),
              minimum_size=1024, compresslevel=5), name='static')

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
