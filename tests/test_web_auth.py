"""Synthetic standalone authentication checks (no planning data or real secrets)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sp5generator.web_auth import install_web_auth


def make_client(monkeypatch, tmp_path, enabled=True, https=False):
    monkeypatch.delenv('SP5_WEB_PASSWORD_FILE', raising=False)
    if enabled:
        password_file = tmp_path / 'synthetic-password'
        password_file.write_text('synthetic-test-password\n')
        monkeypatch.setenv('SP5_WEB_PASSWORD_FILE', str(password_file))
    app = FastAPI()
    install_web_auth(app)

    @app.get('/api/private')
    @app.get('/')
    @app.get('/healthz')
    def resource():
        return {'ok': True}

    return TestClient(app, base_url='https://testserver' if https else 'http://testserver')


def test_disabled_keeps_local_mode(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path, enabled=False)
    assert client.get('/api/private').status_code == 200


def test_auth_login_logout(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    assert client.get('/healthz').status_code == 200
    assert client.get('/api/private').status_code == 401
    assert client.get('/', follow_redirects=False).headers['location'] == '/login'
    assert '<form' in client.get('/login').text
    assert '<script' not in client.get('/login').text
    assert client.post('/login', data={'password': 'wrong'}).status_code == 401
    response = client.post('/login', data={'password': 'synthetic-test-password'}, follow_redirects=False)
    assert response.status_code == 303
    cookie = response.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'SameSite=strict' in cookie and 'Secure' not in cookie
    assert 'synthetic-test-password' not in cookie
    old_token = client.cookies.get('sp5_session')
    assert client.get('/api/private').status_code == 200
    client.post('/logout')
    client.cookies.set('sp5_session', old_token)
    assert client.get('/api/private').status_code == 401


def test_secure_cookie_and_forged_session(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path, https=True)
    client.cookies.set('sp5_session', 'forged')
    assert client.get('/api/private').status_code == 401
    response = client.post('/login', data={'password': 'synthetic-test-password'}, follow_redirects=False)
    assert 'Secure' in response.headers['set-cookie']


def test_rate_limit(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    for _ in range(5):
        assert client.post('/login', data={'password': 'wrong'}).status_code == 401
    response = client.post('/login', data={'password': 'synthetic-test-password'})
    assert response.status_code == 429
    assert response.headers['retry-after'] == '60'


def test_input_limits(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    assert client.post('/login', json={'password': 'x'}).status_code == 415
    assert client.post('/login', data={'password': 'x' * 9000}).status_code == 413
    assert client.post('/login', content='password=a&password=b', headers={'content-type': 'application/x-www-form-urlencoded'}).status_code == 400


@pytest.mark.parametrize('contents', ['', '\n', '\xff', 'a\nb', 'x' * 8193])
def test_bad_password_config_fails_closed(monkeypatch, tmp_path, contents):
    path = tmp_path / 'bad-password'
    path.write_bytes(contents.encode('latin-1'))
    monkeypatch.setenv('SP5_WEB_PASSWORD_FILE', str(path))
    with pytest.raises(RuntimeError, match='nonempty UTF-8 password'):
        install_web_auth(FastAPI())


def test_missing_password_file_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setenv('SP5_WEB_PASSWORD_FILE', str(tmp_path / 'absent'))
    with pytest.raises(RuntimeError):
        install_web_auth(FastAPI())


def test_expiration_and_rotation(monkeypatch, tmp_path):
    import sp5generator.web_auth as auth

    now = [100.0]
    monkeypatch.setattr(auth.time, 'monotonic', lambda: now[0])
    client = make_client(monkeypatch, tmp_path)
    client.post('/login', data={'password': 'synthetic-test-password'})
    old_token = client.cookies.get('sp5_session')
    client.post('/login', data={'password': 'synthetic-test-password'})
    new_token = client.cookies.get('sp5_session')
    assert new_token != old_token
    client.cookies.clear()
    client.cookies.set('sp5_session', old_token)
    assert client.get('/api/private').status_code == 401
    client.cookies.set('sp5_session', new_token)
    assert client.get('/api/private').status_code == 200
    now[0] += 8 * 60 * 60 + 1
    assert client.get('/api/private').status_code == 401


def test_stream_limit_without_content_length(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    response = client.post('/login', content=iter([b'password=', b'x' * 9000]),
                           headers={'content-type': 'application/x-www-form-urlencoded'})
    assert response.status_code == 413
