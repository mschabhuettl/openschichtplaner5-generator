"""HTTP transport tests using freshly generated synthetic responses only."""

import json
from datetime import date
from io import BytesIO
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import pytest

pytest.importorskip("sp5lib")
from sp5generator.api_adapter import (
    APIClient,
    APIImportError,
    _NoRedirect,
    import_api,
    inspect_api,
)
from test_sp5_adapter import SyntheticDatabase


@pytest.fixture
def transport(monkeypatch, tmp_path):
    credential = tmp_path / "token"
    credential.write_text("synthetic-test-token")
    monkeypatch.setenv("SP5_API_URL", "http://source.test/api")
    monkeypatch.setenv("SP5_API_TOKEN_FILE", str(credential))
    source = SyntheticDatabase()
    calls = []
    responses = {
        "/api/auth/me": {"showabs_mode": 0},
        "/api/groups": [{"ID": 1, "NAME": "Team A"}],
        "/api/groups/1/members": source.get_employees(),
        "/api/employees": source.get_employees(),
        "/api/shifts": source.get_shifts(),
        "/api/workplaces": source.get_workplaces(),
        "/api/holidays": source.get_holidays(),
        "/api/staffing-requirements": source.get_staffing_requirements(),
        "/api/staffing-requirements/special": [],
        "/api/restrictions": source.get_restrictions(),
    }

    class Transport:
        def open(self, request, timeout):
            calls.append(request)
            assert request.get_method() == "GET"
            assert request.get_header("Authorization") == "Bearer synthetic-test-token"
            path = urlsplit(request.full_url)
            if path.path == "/api/schedule":
                params = parse_qs(path.query)
                result = source.get_schedule(
                    int(params["year"][0]), int(params["month"][0])
                )
                if params["year"] == ["2026"] and params["month"] == ["1"]:
                    result += [
                        {
                            "employee_id": 101,
                            "date": "2026-01-02",
                            "kind": "shift",
                            "shift_id": 201,
                            "workplace_id": 301,
                        }
                    ]
            else:
                result = responses[path.path]
            return BytesIO(json.dumps(result).encode())

    monkeypatch.setattr("sp5generator.api_adapter.build_opener", lambda *a: Transport())
    return responses, calls


def test_existing_api_import_read_only_history_and_no_credentials(transport):
    assert inspect_api()["groups"] == [{"id": "1", "name": "Team A"}]
    snapshot = import_api(
        date(2026, 1, 6),
        date(2026, 1, 6),
        "1",
        "UTC",
        date(2026, 1, 1),
        date(2026, 1, 5),
        "both",
    )
    assert (
        snapshot.metadata["history_matrix"][0]["suggested_approvals"][0]["confirmed"]
        is False
    )
    assert snapshot.employees[0].approvals == []
    assert snapshot.restrictions[0].level == 1
    assert snapshot.demands[0].maximum == 2
    payload = snapshot.model_dump_json()
    assert "synthetic-test-token" not in payload and "source.test" not in payload
    assert snapshot.unresolved and not snapshot.context_complete
    assert any("plan=both" in c.full_url for c in transport[1])


def test_incomplete_absence_visibility_blocks(transport):
    transport[0]["/api/auth/me"]["showabs_mode"] = 2
    with pytest.raises(APIImportError, match="Abwesenheitsinformationen"):
        inspect_api()


def test_failure_body_and_redirect_not_disclosed(transport, monkeypatch):
    client = APIClient()

    class Broken:
        def open(self, *a, **kw):
            raise HTTPError(
                "http://source.test",
                401,
                "synthetic-test-token",
                {},
                BytesIO(b"private response"),
            )

    client.opener = Broken()
    with pytest.raises(APIImportError) as err:
        client.get("/api/groups")
    assert "401" in str(err.value)
    assert "synthetic-test-token" not in str(
        err.value
    ) and "private response" not in str(err.value)
    with pytest.raises(APIImportError, match="Weiterleitungen"):
        _NoRedirect().redirect_request(None, None, 302, "", {}, "http://other.test")


def test_changed_source_and_incomplete_shape_rejected(transport, monkeypatch):
    client = APIClient()
    client.get("/api/groups")
    transport[0]["/api/groups"] = []
    with pytest.raises(APIImportError, match="verändert"):
        client.verify()
    transport[0]["/api/groups"] = [{"ID": 1}]
    transport[0]["/api/staffing-requirements"] = {"shift_requirements": []}
    with pytest.raises(APIImportError, match="Bedarfsformat"):
        import_api(date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")


def test_configuration_is_only_server_owned(transport, monkeypatch):
    monkeypatch.setenv("SP5_API_URL", "https://user:password@source.test")
    with pytest.raises(APIImportError, match="ohne Zugangsdaten"):
        APIClient()
