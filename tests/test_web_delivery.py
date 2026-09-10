"""HTTP cache correctness and safe project lifecycle routes."""

import gzip

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from sp5generator.webapp import create_app


def test_static_assets_revalidate_and_compress_without_caching_project_data(tmp_path):
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        with client.stream("GET", "/static/app.js", headers={"Accept-Encoding": "gzip"}) as asset:
            compressed = b"".join(asset.iter_raw())
        asset_content = gzip.decompress(compressed)
        assert asset.status_code == 200
        assert asset.headers["Content-Encoding"] == "gzip"
        # Large files stream in chunks and legitimately omit Content-Length.
        assert len(compressed) < len(asset_content)
        assert asset.headers["ETag"].startswith('W/"')
        assert asset.headers["Cache-Control"] == "public, max-age=0, must-revalidate"
        assert "Accept-Encoding" in asset.headers["Vary"]
        unchanged = client.get("/static/app.js", headers={"If-None-Match": asset.headers["ETag"]})
        assert unchanged.status_code == 304
        assert not unchanged.content
        assert unchanged.headers["ETag"] == asset.headers["ETag"]
        assert unchanged.headers["Cache-Control"] == asset.headers["Cache-Control"]
        raw = client.get("/static/app.js", headers={"Accept-Encoding": "identity"})
        assert "Content-Encoding" not in raw.headers
        assert raw.content == asset_content
        assert raw.headers["ETag"] == asset.headers["ETag"]
        for path in ("/", "/api/demo", "/api/status", "/static/missing.js"):
            response = client.get(path)
            assert response.headers["Cache-Control"] == "no-store"
            assert "Content-Encoding" not in response.headers


def test_cached_asset_cannot_bypass_login_or_cross_origin_boundary(tmp_path, monkeypatch):
    password = tmp_path / "password"
    password.write_text("synthetic-password")
    monkeypatch.setenv("SP5_WEB_PASSWORD_FILE", str(password))
    with TestClient(create_app(str(tmp_path / "state"), start_worker=False)) as client:
        assert client.post("/login", data={"password": "synthetic-password"}).status_code == 200
        asset = client.get("/static/app.js")
        assert asset.status_code == 200
        client.post("/logout")
        response = client.get("/static/app.js", headers={"If-None-Match": asset.headers["ETag"]}, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["Cache-Control"] == "no-store"
        assert client.get("/api/status").status_code == 401
        assert client.get("/static/app.js", headers={"Origin": "https://foreign.invalid"}).status_code == 403


def test_project_routes_revision_guards_and_lightweight_job_status(tmp_path):
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        snapshot = client.get("/api/demo").json()
        snapshot["metadata"]["project_name"] = "September planning"
        saved = client.put("/api/snapshots", json=snapshot).json()
        assert client.get("/api/snapshots").json()[0]["project_name"] == "September planning"
        job = client.post("/api/jobs", json={"snapshot_id": saved["id"]}).json()
        status = client.get(f"/api/jobs/{job['id']}/status").json()
        assert status["state"] == "queued" and status["queue_position"] == 1
        assert "result" not in status and "payload" not in status
        service = client.get("/api/status").json()
        assert service["status"] == "ok"
        assert service["jobs"] == {"queued": 1, "running": 0}
        project = f"/api/snapshots/{saved['id']}"
        assert client.post(project + "/archive", json={"revision": saved["revision"]}).status_code == 409
        client.post(f"/api/jobs/{job['id']}/cancel")
        archived = client.post(project + "/archive", json={"revision": saved["revision"]}).json()
        assert client.get("/api/snapshots").json() == []
        assert len(client.get("/api/snapshots", params={"archived": True}).json()) == 1
        assert client.post(project + "/restore", json={"revision": saved["revision"]}).status_code == 409
        copy = client.post(project + "/copy", json={"revision": archived["revision"], "project_name": "Alternative"})
        assert copy.status_code == 200 and copy.json()["metadata"]["project_name"] == "Alternative"
        assert client.post(project + "/restore", json={"revision": archived["revision"]}).status_code == 200
        assert len(client.get("/api/snapshots").json()) == 2
        assert client.get("/api/snapshots", params={"limit": 1001}).status_code == 422
        assert client.get("/api/snapshots", params={"offset": 10**100}).status_code == 422
        assert client.post(project + "/copy", json={}).status_code == 422
        assert client.post(project + "/copy", json={"revision": "3", "project_name": "   "}).status_code == 422
        assert client.get("/api/jobs/missing/status").status_code == 404


@pytest.mark.parametrize("timezone,start,end,expected", [
    ("Europe/Vienna", "2026-03-29T01:30", "2026-03-29T03:30", ("+01:00", "+02:00")),
    ("America/New_York", "2026-01-15T09:00", "2026-01-15T17:00", ("-05:00", "-05:00")),
    ("Europe/Vienna", "2026-03-29T02:30", "2026-03-29T03:30", "existiert"),
    ("Europe/Vienna", "2026-10-25T02:30", "2026-10-25T03:30", "zweimal"),
    ("UTC", "2026-01-01T09:00", "2026-01-01T09:00", "nach"),
    ("UTC", "2026-01-02T09:00", "2026-01-01T09:00", "nach"),
    ("Missing/Synthetic", "2026-01-01T09:00", "2026-01-01T10:00", "zeitzone"),
    ("UTC", "2026-02-30T09:00", "2026-03-01T10:00", "ungültig"),
])
def test_local_interval_resolution_respects_project_timezone_and_dst(tmp_path, timezone, start, end, expected):
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        response = client.post("/api/intervals/resolve", json={"timezone": timezone, "start": start, "end": end})
        if isinstance(expected, tuple):
            assert response.status_code == 200
            assert response.json()["start"].endswith(expected[0])
            assert response.json()["end"].endswith(expected[1])
        else:
            assert response.status_code == 422
            assert expected in response.json()["detail"]


@pytest.mark.parametrize("value", ["2026-01-01", "2026-01-01T09:00Z", "2026-01-01T09:00:30", 12345])
def test_interval_resolution_requires_local_minute_precision(tmp_path, value):
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        response = client.post("/api/intervals/resolve", json={"timezone": "UTC", "start": value, "end": "2026-01-01T17:00"})
        assert response.status_code == 422
