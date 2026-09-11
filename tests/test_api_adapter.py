"""HTTP transport tests using freshly generated synthetic responses only."""

import json
from datetime import date, timedelta
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
        "/api/bookings": [],
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
                result = responses.get(("schedule", params["year"][0], params["month"][0], params["plan"][0]), result)
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


@pytest.mark.parametrize("slot", range(8))
@pytest.mark.parametrize("boundary", [False, True])
def test_http_time_slots_match_library_for_demand_and_boundary(transport, slot, boundary):
    """Do not copy the OSP5 hover's weekday+1 lookup into planning time.

    Every slot differs, including paid versus real minutes. Identical daily
    fixtures would conceal an off-by-one or holiday/default fallback.
    """
    from sp5lib import calculations as calc
    from sp5generator.timeutils import day_minutes

    responses, calls = transport
    duty_day = date(2026, 1, 5) + timedelta(days=slot)
    period = duty_day + timedelta(days=int(boundary))
    holidays = {duty_day: 0} if slot == 7 else {}
    responses["/api/holidays"] = [{"DATE": d.isoformat(), "INTERVAL": 0} for d in holidays]
    native = responses["/api/shifts"][0]
    for index in range(8):
        native[f"STARTEND{index}"] = f"{index + 1:02}:00-{index + 2:02}:30"
        native[f"DURATION{index}"] = index + 1
    # The derived library field is zero-based too. It must not override the
    # full canonical STARTEND slots or supply a spurious default.
    native["TIMES_BY_WEEKDAY"] = {
        str(i): {"start": f"{i + 1:02}:00", "end": f"{i + 2:02}:30"}
        for i in range(7)
    }
    row = responses["/api/staffing-requirements"]["shift_requirements"][0]
    responses["/api/staffing-requirements"]["shift_requirements"] = [
        {**row, "id": 401 + i, "weekday": i} for i in range(8)
    ]
    responses[("schedule", "2026", "1", "ist")] = [{
        "employee_id": 101, "date": duty_day.isoformat(), "kind": "shift",
        "shift_id": 201, "workplace_id": 301,
    }]
    snapshot = import_api(period, period, "1", "UTC",
                          period - timedelta(days=1), period - timedelta(days=1))
    assert calc.day_index(duty_day, holidays) == slot
    expected = calc.parse_startend(native[f"STARTEND{slot}"])
    source = "sp5:existing" if boundary else "sp5:SHIFT"
    duties = [s for s in (snapshot.boundary_work if boundary else snapshot.shifts) if s.source == source]
    assert len(duties) == 1
    duty = duties[0]
    assert [(s.start.hour * 60 + s.start.minute, s.end.hour * 60 + s.end.minute)
            for s in duty.segments] == expected
    assert day_minutes(duty, snapshot.timezone) == {duty_day: 90}
    if boundary:
        assert not hasattr(duty, "paid_minutes")
        assert not snapshot.assignments
        assert duty.kind == "unknown"
        assert snapshot.metadata["provenance"][duty.id]["time_source"] == f"sp5:SHIFT.STARTEND{slot}"
    else:
        assert duty.paid_minutes == (slot + 1) * 60
        assert duty.holiday is (slot == 7)
        assert len(snapshot.assignments) == 1
        assert not snapshot.assignments[0].fixed
    assert not snapshot.employees[0].approvals
    assert all(request.get_method() == "GET" for request in calls)


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
    assert set(snapshot.employees[0].team_ids) == {'sp5:group:1', 'sp5:group:2', 'sp5:group:3'}
    regular = [d for d in snapshot.demands if d.source == 'sp5:SHDEM']
    assert len(regular) == 1
    assert next(s for s in snapshot.shifts if s.id == regular[0].shift_id).team_id == 'sp5:group:2'
    assert not snapshot.assignments
    assert len(snapshot.boundary_work) == 1
    assert snapshot.metadata['history_matrix'][0]['observed_assignment_count'] == 1
    assert not any('/api/groups/4/members' in c.full_url for c in calls)
    assert any('group_id=3' in c.full_url for c in calls)
    described = inspect_api()['groups']
    assert next(g for g in described if g['id'] == '3')['depth'] == 2


@pytest.mark.parametrize("url", ["http://[broken", "http://source.test:wrong", "http://source.test:65536", "http://source.test/\napi"])
def test_malformed_url_is_reported_without_configuration_disclosure(transport, monkeypatch, url):
    monkeypatch.setenv("SP5_API_URL", url)
    with pytest.raises(APIImportError) as error:
        APIClient()
    assert "source.test" not in str(error.value)


@pytest.mark.parametrize("payload", [b'{"ID":1,"ID":2}', b'{"value":NaN}', b'{"value":Infinity}'])
def test_ambiguous_json_is_rejected(transport, payload):
    client = APIClient()
    class Broken:
        def open(self, *args, **kwargs):
            return BytesIO(payload)
    client.opener = Broken()
    with pytest.raises(APIImportError):
        client.get("/api/groups")


def test_transport_retains_specific_redirect_error(transport):
    client = APIClient()
    class Redirect:
        def open(self, *args, **kwargs):
            raise APIImportError("API-Weiterleitungen sind nicht erlaubt.")
    client.opener = Redirect()
    with pytest.raises(APIImportError, match="Weiterleitungen"):
        client.get("/api/groups")


def test_inspection_sanitizes_invalid_hierarchy(transport):
    transport[0]["/api/groups"] = [{"ID": 1, "SUPERID": 1}]
    with pytest.raises(APIImportError, match="Gruppenformat"):
        inspect_api()


def test_requirement_rows_must_be_objects(transport):
    transport[0]["/api/staffing-requirements"] = {
        "shift_requirements": ["invalid"], "daily_requirements": []}
    with pytest.raises(APIImportError, match="Bedarfsformat"):
        import_api(date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")


def test_api_reference_view_is_separate_from_history_and_actual_context(transport):
    responses, calls = transport
    responses[('schedule', '2026', '1', 'soll')] = [
        {'employee_id': 101, 'date': '2026-01-06', 'kind': 'shift', 'shift_id': 201, 'workplace_id': 301},
        {'employee_id': 101, 'date': '2026-01-05', 'kind': 'absence', 'interval': 0},
    ]
    snapshot = import_api(date(2026, 1, 6), date(2026, 1, 6), '1', 'UTC',
                          date(2026, 1, 1), date(2026, 1, 5), 'ist', reference_plan='soll')
    assert snapshot.metadata['reference_plan'] == 'soll'
    assert snapshot.metadata['history_plan'] == 'ist'
    assert len(snapshot.metadata['reference_schedule']) == 1
    assert snapshot.metadata['history_matrix'][0]['observed_assignment_count'] == 1
    assert snapshot.employees[0].unavailable[0].start.hour == 10
    assert not snapshot.employees[0].approvals
    assert not snapshot.context_complete and snapshot.unresolved
    schedules = [parse_qs(urlsplit(c.full_url).query) for c in calls if urlsplit(c.full_url).path == '/api/schedule']
    assert any(q['plan'] == ['soll'] for q in schedules)
    assert any(q['plan'] == ['ist'] for q in schedules)
    with pytest.raises(APIImportError, match='Referenzplansicht'):
        import_api(date(2026, 1, 6), date(2026, 1, 6), '1', 'UTC', reference_plan='both')


@pytest.mark.parametrize("case", ["nominal", "longer", "paid_only", "missing_time", "ambiguous", "deviation"])
def test_special_duty_details_use_live_read_only_endpoint_and_never_guess(transport, case):
    """SPSHI time and paid duration must both agree before nominal substitution."""
    responses, calls = transport
    special = {"employee_id": 101, "date": "2026-01-06", "kind": "special_shift",
               "shift_id": 201, "workplace_id": 301,
               "spshi_type": 1 if case == "deviation" else 0}
    responses[("schedule", "2026", "1", "ist")] = [special]
    detail = {"id": 901, "employee_id": 101, "date": "2026-01-06",
              "shift_id": 201, "workplace_id": 301, "type": special["spshi_type"],
              "startend": "08:00-10:00;11:00-13:00", "duration": 4}
    if case == "longer":
        detail["startend"] = "08:00-10:00;11:00-14:00"
    elif case == "paid_only":
        detail["duration"] = 5
    elif case == "missing_time":
        detail.pop("startend")
    responses["/api/einsatzplan"] = [detail]
    if case == "ambiguous":
        responses["/api/einsatzplan"].append({**detail, "id": 902, "duration": 5})

    snapshot = import_api(date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")

    assert bool(snapshot.assignments) == (case == "nominal")
    assert any(issue.startswith("Sonderdienst") for issue in snapshot.unresolved) == (case != "nominal")
    assert snapshot.employees[0].approvals == []
    detail_calls = [urlsplit(c.full_url) for c in calls if urlsplit(c.full_url).path == "/api/einsatzplan"]
    assert detail_calls
    assert all(parse_qs(c.query) == {"date": ["2026-01-06"], "group_id": ["1"]} for c in detail_calls)
    assert all(c.get_method() == "GET" and "/admin/orm" not in c.full_url for c in calls)
