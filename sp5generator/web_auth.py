"""Optional single-user authentication; sessions intentionally expire on restart."""
import hashlib
import hmac
import os
from pathlib import Path
import secrets
import time
from collections import OrderedDict
from urllib.parse import parse_qs

from fastapi import Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

_COOKIE = 'sp5_session'
_SESSION_SECONDS = 8 * 60 * 60
_MAX_BODY = 8192
_MAX_ENTRIES = 1024
_LOGIN_HTML = '''<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<link rel="stylesheet" href="/static/login.css">
<title>Anmelden · OpenSchichtplaner5 Generator</title></head><body><main>
<div class="brand"><span class="brand-mark" aria-hidden="true">S</span><span>OpenSchichtplaner5<span class="brand-subtitle">Generator</span></span></div>
<div class="login-card"><p class="eyebrow">IHR PLANUNGSBEREICH</p><h1>Willkommen zurück.</h1>
<p class="intro">Melden Sie sich an, um Ihre Projekte und Dienstpläne zu öffnen.</p>
<h2>Anmelden</h2>
<form method="post" action="/login"><label for="password">Passwort</label>
<input id="password" name="password" type="password" autocomplete="current-password" required autofocus>
<button type="submit">Arbeitsbereich öffnen <span aria-hidden="true">→</span></button></form></div>
<p class="footer">OpenSchichtplaner5 Generator · Lokale Dienstplanung</p></main></body></html>'''


def install_web_auth(app):
    """Install before host/origin middleware, which must wrap authentication.

    SP5_WEB_PASSWORD_FILE is a UTF-8 file (one trailing line ending ignored).
    Unset means local development mode. Configured but invalid fails closed.
    """
    filename = os.environ.get('SP5_WEB_PASSWORD_FILE')
    app.state.web_auth_enabled = filename is not None
    if filename is None:
        return
    try:
        with Path(filename).open('rb') as password_file:
            raw_password = password_file.read(_MAX_BODY + 1)
        if len(raw_password) > _MAX_BODY:
            raise ValueError
        password = raw_password.decode('utf-8').removesuffix('\n').removesuffix('\r')
        del raw_password
        if not password or len(password.encode()) > _MAX_BODY or '\n' in password or '\r' in password:
            raise ValueError
    except (OSError, UnicodeError, ValueError):
        raise RuntimeError('SP5_WEB_PASSWORD_FILE must contain a nonempty UTF-8 password') from None
    salt = secrets.token_bytes(32)
    password_hash = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    del password
    sessions = OrderedDict()
    attempts = OrderedDict()

    def trim(mapping, now):
        for key in [key for key, expiry in mapping.items() if expiry <= now]:
            del mapping[key]

    @app.middleware('http')
    async def authentication(request: Request, call_next):
        if request.url.path in {'/login', '/logout', '/healthz', '/static/login.css'}:
            return await call_next(request)
        now = time.monotonic()
        trim(sessions, now)
        token = request.cookies.get(_COOKIE, '')
        if token and token in sessions:
            return await call_next(request)
        if request.url.path.startswith('/api/'):
            return JSONResponse({'detail': 'Authentication required'}, status_code=401)
        return RedirectResponse('/login', status_code=303)

    @app.get('/login', include_in_schema=False)
    async def login_page():
        return HTMLResponse(_LOGIN_HTML)

    @app.post('/login', include_in_schema=False)
    async def login(request: Request):
        now = time.monotonic()
        # Do not trust forwarding headers for client identity. Bound both memory
        # and expensive password checks, including requests from many clients.
        remote = request.client.host if request.client else 'unknown'
        expired = [key for key, (_, expiry) in attempts.items() if expiry <= now]
        for key in expired:
            del attempts[key]
        count, expiry = attempts.get(remote, (0, now + 60))
        if count >= 5 or (remote not in attempts and len(attempts) >= _MAX_ENTRIES):
            return HTMLResponse(_LOGIN_HTML.replace('<h2>Anmelden</h2>', '<h2>Anmelden</h2><p class="error" role="alert">Zu viele Anmeldeversuche. Bitte in einer Minute erneut versuchen.</p>'), status_code=429, headers={'Retry-After': '60'})
        attempts[remote] = (count + 1, expiry)
        if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/x-www-form-urlencoded':
            return JSONResponse({'detail': 'Form submission required'}, status_code=415)
        try:
            if int(request.headers.get('content-length', '0')) > _MAX_BODY:
                return JSONResponse({'detail': 'Login form too large'}, status_code=413)
        except ValueError:
            return JSONResponse({'detail': 'Invalid login form'}, status_code=400)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > _MAX_BODY:
                return JSONResponse({'detail': 'Login form too large'}, status_code=413)
        try:
            fields = parse_qs(body.decode('utf-8'), max_num_fields=4, strict_parsing=True)
            supplied = fields.get('password', [])
            if len(supplied) != 1:
                raise ValueError
            candidate = await run_in_threadpool(hashlib.scrypt, supplied[0].encode(), salt=salt, n=16384, r=8, p=1)
        except (UnicodeError, ValueError):
            return JSONResponse({'detail': 'Invalid login form'}, status_code=400)
        if not hmac.compare_digest(candidate, password_hash):
            return HTMLResponse(_LOGIN_HTML.replace('<h2>Anmelden</h2>', '<h2>Anmelden</h2><p class="error" role="alert">Passwort nicht korrekt. Bitte erneut versuchen.</p>'), status_code=401)
        trim(sessions, now)
        if len(sessions) >= _MAX_ENTRIES:
            sessions.popitem(last=False)
        # Rotate any existing session on login.
        sessions.pop(request.cookies.get(_COOKIE, ''), None)
        token = secrets.token_urlsafe(32)
        sessions[token] = now + _SESSION_SECONDS
        response = RedirectResponse('/', status_code=303)
        response.set_cookie(_COOKIE, token, max_age=_SESSION_SECONDS, httponly=True,
                            secure=request.url.scheme == 'https', samesite='strict')
        return response

    @app.post('/logout', include_in_schema=False)
    async def logout(request: Request):
        sessions.pop(request.cookies.get(_COOKIE, ''), None)
        response = RedirectResponse('/login', status_code=303)
        response.delete_cookie(_COOKIE, httponly=True, secure=request.url.scheme == 'https', samesite='strict')
        return response
