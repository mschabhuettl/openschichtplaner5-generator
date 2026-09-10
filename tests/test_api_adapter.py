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
    assert [(g["id"], g["name"]) for g in inspect_api()["groups"]] == [("1", "Team A")]
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


def test_explicit_dev_mode_without_token_file(monkeypatch):
    monkeypatch.setenv('SP5_API_URL', 'http://source.test')
    monkeypatch.setenv('SP5_API_DEV_MODE', 'true')
    monkeypatch.delenv('SP5_API_TOKEN_FILE', raising=False)
    calls = []
    class DevTransport:
        def open(self, request, timeout):
            path = urlsplit(request.full_url).path
            calls.append(path)
            assert request.get_method() == 'GET'
            if path == '/api/dev/mode':
                assert request.get_header('Authorization') is None
                result = {'dev_mode': True}
            else:
                assert request.get_header('Authorization') == 'Bearer __dev_mode__'
                result = {'showabs_mode': 0} if path == '/api/auth/me' else [{'ID': 1, 'NAME': 'Team A'}]
            return BytesIO(json.dumps(result).encode())
    monkeypatch.setattr('sp5generator.api_adapter.build_opener', lambda *a: DevTransport())
    assert [(g['id'], g['name']) for g in inspect_api()['groups']] == [('1', 'Team A')]
    assert calls[0] == '/api/dev/mode'


def test_dev_mode_never_falls_back_for_regular_api(monkeypatch):
    monkeypatch.setenv('SP5_API_URL', 'http://source.test')
    monkeypatch.setenv('SP5_API_DEV_MODE', 'true')
    class NormalTransport:
        def open(self, request, timeout):
            assert request.get_header('Authorization') is None
            assert request.full_url.endswith('/api/dev/mode')
            return BytesIO(b'{"dev_mode":false}')
    monkeypatch.setattr('sp5generator.api_adapter.build_opener', lambda *a: NormalTransport())
    with pytest.raises(APIImportError, match='keinen aktiven Dev-Modus'):
        inspect_api()
    monkeypatch.setenv('SP5_API_DEV_MODE', 'false')
    monkeypatch.delenv('SP5_API_TOKEN_FILE', raising=False)
    with pytest.raises(APIImportError, match='TOKEN_FILE'):
        APIClient()


def test_parent_team_imports_nested_people_without_duplicates(transport):
    responses, calls = transport
    people = responses['/api/employees']
    responses['/api/groups'] = [
        {'ID': 1, 'NAME': 'Team A', 'SUPERID': 0},
        {'ID': 2, 'NAME': 'Team B', 'SUPERID': 1},
        {'ID': 3, 'NAME': 'Team C', 'SUPERID': 2},
        {'ID': 4, 'NAME': 'Team D', 'SUPERID': 0},
    ]
    responses['/api/groups/1/members'] = []
    responses['/api/groups/2/members'] = people
    responses['/api/groups/3/members'] = people
    responses['/api/groups/4/members'] = []
    responses['/api/staffing-requirements']['shift_requirements'][0]['group_id'] = 2
    snapshot = import_api(date(2026, 1, 6), date(2026, 1, 6), '1', 'UTC', date(2026, 1, 1), date(2026, 1, 5))
    assert len(snapshot.employees) == 1
    assert set(snapshot.employees[0].team_ids) == {'sp5:group:2', 'sp5:group:3'}
    regular = [d for d in snapshot.demands if d.source == 'sp5:SHDEM']
    assert len(regular) == 1
    assert next(s for s in snapshot.shifts if s.id == regular[0].shift_id).team_id == 'sp5:group:2'
    assert len(snapshot.assignments) == 1
    assert snapshot.metadata['history_matrix'][0]['observed_assignment_count'] == 1
    assert not any('/api/groups/4/members' in c.full_url for c in calls)
    assert any('group_id=3' in c.full_url for c in calls)
    described = inspect_api()['groups']
    assert next(g for g in described if g['id'] == '3')['depth'] == 2
