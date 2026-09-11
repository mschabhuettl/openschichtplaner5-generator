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
        "/api/leave-types": [],
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


def test_repeated_responses_do_not_prove_atomic_source_revision(monkeypatch):
    """Characterize the existing guard, not an endorsement of mixed snapshots.

    The source alternates between two internally consistent revisions. Each
    endpoint repeats, but the cached pair never existed together at the source.
    No amount of hashing those responses establishes a source transaction.
    """
    client = object.__new__(APIClient)
    client.cache = {}
    revisions = [
        {"/api/shifts": [{"ID": 1}], "/api/schedule": [{"shift_id": 1}]},
        {"/api/shifts": [{"ID": 2}], "/api/schedule": [{"shift_id": 2}]},
    ]
    reads = []

    def read(path):
        revision = revisions[len(reads) % 2]
        reads.append(path)
        return revision[path]

    monkeypatch.setattr(client, "_read", read)
    client.get("/api/shifts")
    client.get("/api/schedule")
    assert all(client.cache != revision for revision in revisions)
    assert client.cache["/api/shifts"][0]["ID"] != client.cache["/api/schedule"][0]["shift_id"]
    fingerprint = client.verify()
    assert len(fingerprint) == 64
    assert client.verify() == fingerprint
    assert reads == ["/api/shifts", "/api/schedule"] * 3


def test_api_import_retains_nontransactional_source_blocker(transport):
    snapshot = import_api(date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert snapshot.metadata["source_consistency"] == (
        "repeated-response-comparison; no API transaction"
    )
    assert any("Quelltransaktion" in reason for reason in snapshot.unresolved)


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


@pytest.mark.parametrize("special_first", [False, True])
@pytest.mark.parametrize("identity", ["same", "workplace", "service"])
def test_special_replacement_boundary_matches_library_person_day(transport, identity, special_first):
    """Day-wide replacement; paid and real durations coincide only in this fixture."""
    from sp5lib import calculations as calc

    responses, calls = transport
    day = date(2026, 1, 5)
    normal = {"employee_id": 101, "date": day.isoformat(), "kind": "shift",
              "shift_id": 201, "workplace_id": 301}
    special = {**normal, "kind": "special_shift", "spshi_type": 0}
    if identity == "workplace":
        special["workplace_id"] = 302
    elif identity == "service":
        special["shift_id"] = 202
        responses["/api/shifts"].append({**responses["/api/shifts"][0], "ID": 202})
    responses[("schedule", "2026", "1", "ist")] = (
        [special, normal] if special_first else [normal, special])
    responses["/api/einsatzplan"] = [{
        "id": 901, "employee_id": 101, "date": day.isoformat(),
        "shift_id": special["shift_id"], "workplace_id": special["workplace_id"],
        "type": 0, "startend": "08:00-10:00;11:00-13:00", "duration": 4,
    }]
    expected_hours = calc.get_work_hours(
        calc.EmployeeContext(workdays=(True,) * 8, calcbase=0, hrs_day=8), day, day,
        holidays={}, shifts_by_id={s["ID"]: s for s in responses["/api/shifts"]},
        manual_shifts=[{"DATE": day.isoformat(), "SHIFTID": normal["shift_id"]}],
        special_shifts=[{"DATE": day.isoformat(), "SHIFTID": special["shift_id"],
                         "DURATION": 4, "TYPE": 0}],
    )
    assert expected_hours == 4
    snapshot = import_api(date(2026, 1, 6), date(2026, 1, 6), "1", "UTC")
    assert not snapshot.employees[0].approvals
    assert not any(issue.startswith("Sonderdienst") for issue in snapshot.unresolved)
    assert all(c.get_method() == "GET" for c in calls)
    actual_minutes = sum((segment.end - segment.start).total_seconds() / 60
                         for work in snapshot.boundary_work for segment in work.segments)
    assert actual_minutes == expected_hours * 60
    provenance = snapshot.metadata["provenance"][snapshot.boundary_work[0].id]
    assert provenance["replaced_normal_rows"] == [{
        field: normal.get(field)
        for field in ("employee_id", "date", "shift_id", "workplace_id", "group_id")
    }]


@pytest.mark.parametrize("plan", ["ist", "soll"])
@pytest.mark.parametrize("special_type,service", [(0, 0), (1, 201), (0, 201)])
def test_boundary_replacement_keeps_blockers_additions_and_selected_references(
    transport, plan, special_type, service
):
    responses, _ = transport
    normal = {"employee_id": 101, "date": "2026-01-05", "kind": "shift",
              "shift_id": 201, "workplace_id": 301}
    special = {**normal, "kind": "special_shift", "shift_id": service,
               "spshi_type": special_type}
    reference = {**normal, "date": "2026-01-06"}
    responses[("schedule", "2026", "1", "ist")] = [normal, special, reference]
    responses[("schedule", "2026", "1", "soll")] = [reference]
    responses["/api/einsatzplan"] = [{
        "id": 901, "employee_id": 101, "date": "2026-01-05",
        "shift_id": service, "workplace_id": 301, "type": special_type,
        # Non-nominal replacement cannot be silently accepted.
        "startend": "08:00-14:00", "duration": 6,
    }]
    snapshot = import_api(
        date(2026, 1, 6), date(2026, 1, 6), "1", "UTC", reference_plan=plan
    )
    assert any(issue.startswith("Sonderdienst") for issue in snapshot.unresolved)
    assert len(snapshot.boundary_work) == (1 if service == 0 else 0)
    assert len(snapshot.metadata["reference_schedule"]) == 1
    assert snapshot.metadata["reference_schedule"][0]["date"] == "2026-01-06"
    assert snapshot.employees[0].approvals == []
    assert any(row["kind"] == "shift" and row["date"] == "2026-01-05"
               for row in snapshot.metadata["context_schedule"])


def _import_in_period_replacement(transport, plan, special_first, mode):
    responses, calls = transport
    day = date(2026, 1, 6)
    normal = {"employee_id": 101, "date": day.isoformat(), "kind": "shift",
              "shift_id": 201, "workplace_id": 301}
    special = {**normal, "kind": "special_shift", "shift_id": 202, "spshi_type": 0}
    responses["/api/shifts"].append({**responses["/api/shifts"][0], "ID": 202})
    requirements = responses["/api/staffing-requirements"]["shift_requirements"]
    requirements.append({**requirements[0], "id": 402, "shift_id": 202})
    responses[("schedule", "2026", "1", "ist")] = (
        [special, normal] if special_first else [normal, special])
    responses[("schedule", "2026", "1", "soll")] = [normal]
    responses["/api/einsatzplan"] = [{
        "id": 901, "employee_id": 101, "date": day.isoformat(), "shift_id": 202,
        "workplace_id": 301, "type": 0,
        "startend": "08:00-10:00;11:00-13:00", "duration": 4,
    }]
    snapshot = import_api(day, day, "1", "UTC", reference_plan=plan, existing_plan_mode=mode)
    return snapshot, calls


@pytest.mark.parametrize("plan", ["ist", "soll"])
@pytest.mark.parametrize("special_first", [False, True])
@pytest.mark.parametrize("mode", ["reference", "fixed"])
def test_in_period_replacement_reference_respects_selected_plan(transport, plan, special_first, mode):
    """Ist hours replace normal work; preserve separate Soll/source special context."""
    snapshot, calls = _import_in_period_replacement(transport, plan, special_first, mode)
    assert all(c.get_method() == "GET" for c in calls)
    assert not snapshot.employees[0].approvals
    assert not snapshot.profiles[0].confirmed
    assert len(snapshot.demands) == 2  # Baseline selection must not invent/remove demand.
    assert len(snapshot.metadata["context_schedule"]) == 2  # Keep Ist special context.
    # The source API also exposes special duties in Soll. Do not infer that
    # its normal target duty may be deleted by the Ist replacement rule.
    expected_services = [202] if plan == "ist" else [201, 202]
    assert sorted(r["shift_id"] for r in snapshot.metadata["reference_schedule"]) == expected_services
    assert len(snapshot.assignments) == len(expected_services)
    demands = {d.id: d for d in snapshot.demands}
    shifts = {s.id: s for s in snapshot.shifts}
    paid = sum(shifts[demands[a.demand_id].shift_id].paid_minutes for a in snapshot.assignments)
    assert paid == (240 if plan == "ist" else 480)
    assert all(a.fixed == (mode == "fixed") for a in snapshot.assignments)
    replacement = next(r for r in snapshot.metadata["reference_schedule"] if r["kind"] == "special_shift")
    assert len(replacement["replaced_normal_rows"]) == (1 if plan == "ist" else 0)


@pytest.mark.parametrize("plan", ["ist", "soll"])
@pytest.mark.parametrize("replacement", [False, True])
@pytest.mark.parametrize("mode", ["reference", "fixed"])
def test_in_period_unresolved_special_never_becomes_free_time(transport, plan, replacement, mode):
    responses, _ = transport
    day = date(2026, 1, 6)
    normal = {"employee_id": 101, "date": day.isoformat(), "kind": "shift",
              "shift_id": 201, "workplace_id": 301}
    special = {**normal, "kind": "special_shift", "spshi_type": 0,
               "shift_id": 201 if replacement else 0}
    responses[("schedule", "2026", "1", "ist")] = [normal, special]
    responses[("schedule", "2026", "1", "soll")] = [normal]
    responses["/api/einsatzplan"] = [{
        "id": 901, "employee_id": 101, "date": day.isoformat(),
        "shift_id": special["shift_id"], "workplace_id": 301, "type": 0,
        "startend": "08:00-14:00", "duration": 4,
    }]
    snapshot = import_api(day, day, "1", "UTC", reference_plan=plan, existing_plan_mode=mode)
    assert any(issue.startswith("Sonderdienst") for issue in snapshot.unresolved)
    assert len(snapshot.metadata["context_schedule"]) == 2
    expected = 0 if replacement and plan == "ist" else 1
    assert len(snapshot.metadata["reference_schedule"]) == expected
    assert len(snapshot.assignments) == expected
    assert not snapshot.employees[0].approvals
    assert not snapshot.profiles[0].confirmed


@pytest.mark.parametrize("special_type", [0, 1])
@pytest.mark.parametrize("special_shift_id", [0, 202])
def test_library_special_replacement_is_day_wide_and_not_type_selected(special_type, special_shift_id):
    """Independent source oracle for the pending normalization, no real fixtures."""
    from sp5lib import calculations as calc

    day = date(2026, 1, 5)
    shifts = {sid: {"ID": sid, "DURATION0": 4, "STARTEND0": "08:00-12:00"}
              for sid in (201, 202)}
    hours = calc.get_work_hours(
        calc.EmployeeContext(workdays=(True,) * 8, calcbase=0, hrs_day=8), day, day,
        holidays={}, shifts_by_id=shifts,
        manual_shifts=[{"DATE": day.isoformat(), "SHIFTID": 201, "WORKPLACID": 301},
                       {"DATE": day.isoformat(), "SHIFTID": 202, "WORKPLACID": 302}],
        special_shifts=[{"DATE": day.isoformat(), "SHIFTID": special_shift_id,
                         "WORKPLACID": 303, "DURATION": 3, "TYPE": special_type}],
    )
    assert hours == (3 if special_shift_id else 11)


@pytest.mark.parametrize("plan", ["ist", "soll"])
@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("weekly_limit", [239, 240])
def test_replacement_fixed_import_enforces_hard_limits_through_solver(transport, plan, partial, weekly_limit):
    """Explicit synthetic setup only: imported history never grants permission."""
    from sp5generator.solver import solve
    from sp5generator.validator import validate

    snapshot, _ = _import_in_period_replacement(transport, plan, False, "fixed")
    assert not snapshot.employees[0].approvals
    assert not snapshot.profiles[0].confirmed
    assert solve(snapshot, 3, partial=partial).solver_status == "MODEL_INVALID"
    _configure_synthetic_replacement(snapshot, weekly_limit)
    employee = snapshot.employees[0]
    fixed = [(a.employee_id, a.demand_id) for a in snapshot.assignments]
    checked = validate(snapshot, snapshot.assignments)
    codes = {d.code for d in checked.diagnostics}
    assert ("weekly_limit" in codes) is (weekly_limit == 239 or plan == "soll")
    result = solve(snapshot, 3, partial=partial)
    if plan == "ist" and partial and weekly_limit == 240:
        assert result.solver_status == "OPTIMAL", (checked.diagnostics, result.validation.diagnostics)
        assert [(a.employee_id, a.demand_id) for a in result.assignments] == fixed
        assert all(a.fixed for a in result.assignments)
        assert sum(result.vacancies.values()) == 1
        assert result.validation.valid and not result.validation.complete
        assert validate(snapshot, result.assignments).valid
        assert result.metrics["employees"][employee.id]["paid_minutes"] == 240
    else:
        # Partial relaxes demand coverage, never fixed work or a hard cap.
        assert result.solver_status == "INFEASIBLE"


def _configure_synthetic_replacement(snapshot, weekly_limit):
    from sp5generator.models import Approval

    # Fixture declares complete context, zero credits/balances and exact
    # workplace permissions. No real import is confirmed by this test.
    snapshot.context_complete = True
    snapshot.unresolved = []
    profile = snapshot.profiles[0]
    profile.confirmed = True
    profile.source = "synthetic-test"
    profile.max_weekly_minutes = weekly_limit
    assert profile.min_rest_minutes == 660
    assert profile.weekly_rest_minutes == 2160
    # Source times alone do not classify duties; the synthetic setup does.
    for duty in snapshot.shifts:
        duty.kind = "day"
    employee = snapshot.employees[0]
    employee.approvals = [Approval(
        function_id=p.function_id, workplace_id=p.workplace_id,
        valid_from=snapshot.context_start, valid_until=snapshot.context_end,
    ) for p in snapshot.positions]


@pytest.mark.parametrize("termination", ["first_feasible", "quality_unknown", "first_unknown"])
def test_imported_fixed_replacement_timeout_preserves_only_valid_incumbent(transport, monkeypatch, termination):
    from ortools.sat.python import cp_model
    from sp5generator.solver import solve
    from sp5generator.validator import validate

    snapshot, _ = _import_in_period_replacement(transport, "ist", False, "fixed")
    _configure_synthetic_replacement(snapshot, 240)
    fixed = [(a.employee_id, a.demand_id) for a in snapshot.assignments]
    original = cp_model.CpSolver.solve
    calls = []

    def controlled_status(self, model, *args, **kwargs):
        calls.append(1)
        if termination == "first_unknown" or (termination == "quality_unknown" and len(calls) == 2):
            return cp_model.UNKNOWN
        status = original(self, model, *args, **kwargs)
        assert status == cp_model.OPTIMAL
        return cp_model.FEASIBLE if termination == "first_feasible" else status

    monkeypatch.setattr(cp_model.CpSolver, "solve", controlled_status)
    result = solve(snapshot, 3, partial=True)
    assert len(calls) == (2 if termination == "quality_unknown" else 1)
    if termination == "first_unknown":
        assert result.solver_status == "UNKNOWN"
        assert not result.assignments
        assert not result.validation.valid
        assert result.metrics["planning_diagnostics"]["employees"][snapshot.employees[0].id]["reason"] == "no_valid_plan"
        return
    assert result.solver_status == "FEASIBLE"
    if termination == "quality_unknown":
        assert result.parameters["last_optimization_status"] == "UNKNOWN"
    else:
        assert result.metrics["objective_phase"] == "vacancies"
    assert [(a.employee_id, a.demand_id) for a in result.assignments] == fixed
    assert all(a.fixed for a in result.assignments)
    assert sum(result.vacancies.values()) == 1
    assert result.validation.valid and not result.validation.complete
    assert validate(snapshot, result.assignments).valid
    # The independent check must reject the same incumbent against a tighter
    # real-time cap; time-limited status cannot authorize a relaxed hard rule.
    snapshot.profiles[0].max_weekly_minutes = 239
    checked = validate(snapshot, result.assignments)
    assert not checked.valid
    assert any(d.code == "weekly_limit" for d in checked.diagnostics)


@pytest.mark.parametrize("slot", range(8))
@pytest.mark.parametrize("restricted_slot", range(8))
def test_http_restrictions_use_duty_start_slot_not_midnight_spill(transport, slot, restricted_slot):
    """Characterize the source contract, not the contradictory library docstring.

    A holiday replaces the weekday slot; a second worked date does not turn a
    duty-specific RESTR into a date-wide absence. Every duty crosses midnight.
    """
    from sp5lib import calculations as calc

    responses, calls = transport
    duty_day = date(2026, 1, 5) + timedelta(days=slot)
    next_day = duty_day + timedelta(days=1)
    # For ordinary starts the spill day is a holiday, deliberately different
    # from the start's slot. Slot 7 starts on a holiday Monday instead.
    holidays = {duty_day if slot == 7 else next_day: 0}
    responses["/api/holidays"] = [{"DATE": d.isoformat(), "INTERVAL": 0} for d in holidays]
    native = responses["/api/shifts"][0]
    for index in range(8):
        native[f"STARTEND{index}"] = "22:00-06:00"
        native[f"DURATION{index}"] = 3  # Paid time does not determine the slot.
    row = responses["/api/staffing-requirements"]["shift_requirements"][0]
    responses["/api/staffing-requirements"]["shift_requirements"] = [{**row, "weekday": slot}]
    restriction = responses["/api/restrictions"][0]
    responses["/api/restrictions"] = [{**restriction, "weekday": restricted_slot, "restrict": 2}]
    responses[("schedule", "2026", "1", "ist")] = []
    snapshot = import_api(duty_day, duty_day, "1", "Europe/Vienna",
                          duty_day - timedelta(days=1), duty_day - timedelta(days=1))
    assert len(snapshot.shifts) == 1
    duty = snapshot.shifts[0]
    assert duty.segments[0].start.date() == duty_day
    assert duty.segments[0].end.date() == next_day
    assert duty.paid_minutes == 180
    assert calc.day_index(duty_day, holidays) == slot
    expected = restricted_slot == slot
    assert calc.is_restricted([{"SHIFTID": 201, "WEEKDAY": restricted_slot, "RESTRICT": 2}],
                              201, calc.day_index(duty_day, holidays)) is expected
    assert len(snapshot.restrictions) == int(expected)
    if expected:
        mapped = snapshot.restrictions[0]
        assert mapped.shift_id == duty.id
        assert mapped.employee_id == snapshot.employees[0].id
        assert mapped.level == 2 and not mapped.approved
    assert not snapshot.employees[0].approvals
    assert all(request.get_method() == "GET" for request in calls)


@pytest.mark.parametrize("grade", [0, 1, 2])
@pytest.mark.parametrize("multiple_groups", [False, True])
def test_http_split_duty_restriction_covers_each_group_variant(transport, grade, multiple_groups):
    responses, _ = transport
    day = date(2026, 1, 6)
    groups = [1, 2] if multiple_groups else [1]
    responses["/api/groups"] = [{"ID": gid, "NAME": f"Team {gid}"} for gid in groups]
    responses["/api/groups/2/members"] = responses["/api/groups/1/members"]
    row = responses["/api/staffing-requirements"]["shift_requirements"][0]
    responses["/api/staffing-requirements"]["shift_requirements"] = [
        {**row, "id": 401 + gid, "group_id": gid} for gid in groups
    ]
    native = responses["/api/shifts"][0]
    native["STARTEND7"] = "08:00-10:00 22:00-06:00"
    native["DURATION7"] = 4
    responses["/api/restrictions"][0]["restrict"] = grade
    responses[("schedule", "2026", "1", "ist")] = []
    snapshot = import_api(day, day, timezone="Europe/Vienna",
                          history_start=day - timedelta(days=1),
                          history_end=day - timedelta(days=1),
                          team_ids=[str(gid) for gid in groups])
    assert len(snapshot.shifts) == len(groups)
    assert len(snapshot.restrictions) == len(groups)
    counts = snapshot.metadata["restriction_mapping_counts"]
    assert counts["mapped_rows"] == 1
    assert counts["mapped_instances"] == len(groups)
    assert sum(counts.values()) == 1 + len(groups)
    assert {r.shift_id for r in snapshot.restrictions} == {s.id for s in snapshot.shifts}
    assert all(r.level == grade and not r.approved for r in snapshot.restrictions)
    assert all(len(s.segments) == 2 and s.paid_minutes == 240 for s in snapshot.shifts)
    assert all(s.segments[1].end.date() == day + timedelta(days=1) for s in snapshot.shifts)
    assert all(not e.approvals for e in snapshot.employees)


@pytest.mark.parametrize("override,category,blocked", [
    ({"employee_id": 999}, "outside_employee_scope", False),
    ({"shift_id": 999}, "outside_shift_scope", False),
    ({"weekday": 0}, "outside_day_scope", False),
    *[({"weekday": value}, "invalid_weekday", True)
      for value in (8, -1, None, "7", True, 7.0)],
    *[({"restrict": value}, "invalid_grade", True)
      for value in (3, -1, None, "2", True, 2.0)],
    ({"employee_id": 999, "weekday": 8}, "outside_employee_scope", False),
    ({"shift_id": 999, "weekday": 8}, "outside_shift_scope", False),
    ({"weekday": 0, "restrict": 3}, "outside_day_scope", False),
])
def test_http_restriction_mapping_diagnoses_scope_and_invalid_rows(
    transport, override, category, blocked
):
    responses, _ = transport
    responses["/api/restrictions"][0].update(override)
    responses[("schedule", "2026", "1", "ist")] = []
    day = date(2026, 1, 6)  # Fixture holiday: the only generated slot is 7.
    snapshot = import_api(day, day, "1", history_start=day - timedelta(days=1),
                          history_end=day - timedelta(days=1))
    assert len(snapshot.shifts) == 1
    assert not snapshot.restrictions
    assert any("RESTR" in issue for issue in snapshot.unresolved) == blocked
    counts = snapshot.metadata["restriction_mapping_counts"]
    assert counts[category] == 1
    assert sum(counts.values()) == 1
    assert not snapshot.employees[0].approvals


@pytest.mark.parametrize("partial", [False, True])
def test_invalid_imported_restriction_blocks_otherwise_valid_planning(transport, partial):
    from sp5generator.solver import solve
    from test_core_rules import case

    responses, _ = transport
    responses["/api/restrictions"][0]["weekday"] = 8
    day = date(2026, 1, 6)
    imported = import_api(day, day, "1", history_start=day - timedelta(days=1),
                          history_end=day - timedelta(days=1))
    # Isolate this import blocker from the separately unconfirmed native setup.
    configured = case(1)
    assert solve(configured, 3, partial=partial).solver_status == "OPTIMAL"
    configured.unresolved = [x for x in imported.unresolved if x.startswith("RESTR ")]
    assert len(configured.unresolved) == 1
    result = solve(configured, 3, partial=partial)
    assert result.solver_status == "MODEL_INVALID"
    assert not result.assignments
    assert not result.validation.valid


@pytest.mark.parametrize("reference_plan", ["ist", "soll"])
@pytest.mark.parametrize("cause", [
    "no_demand", "other_team", "other_day", "unknown_restriction_shift",
    "missing_demand_shift", "missing_workplace", "missing_window", "zero_maximum",
])
def test_http_restriction_shift_scope_does_not_identify_root_cause(
    transport, reference_plan, cause
):
    """Keep absence of demand distinct from unresolved source references.

    The same aggregate counter currently covers different upstream causes.
    A zero-capacity demand, in contrast, still has a generated duty and RESTR.
    """
    responses, calls = transport
    requirements = responses["/api/staffing-requirements"]["shift_requirements"]
    row = requirements[0]
    if cause == "no_demand":
        requirements.clear()
    elif cause == "other_team":
        row["group_id"] = 2
    elif cause == "other_day":
        row["weekday"] = 0
    elif cause == "unknown_restriction_shift":
        responses["/api/restrictions"][0]["shift_id"] = 999
    elif cause == "missing_demand_shift":
        responses["/api/shifts"] = []
    elif cause == "missing_workplace":
        responses["/api/workplaces"] = []
    elif cause == "missing_window":
        responses["/api/shifts"][0]["STARTEND7"] = ""
    elif cause == "zero_maximum":
        row.update(min=0, max=0)
    responses["/api/restrictions"][0]["restrict"] = 2
    responses[("schedule", "2026", "1", reference_plan)] = []
    day = date(2026, 1, 6)
    snapshot = import_api(day, day, "1", history_start=day - timedelta(days=1),
                          history_end=day - timedelta(days=1),
                          reference_plan=reference_plan)
    generated = cause in ("unknown_restriction_shift", "zero_maximum")
    assert len(snapshot.shifts) == int(generated)
    assert len(snapshot.demands) == int(generated)
    assert len(snapshot.restrictions) == int(cause == "zero_maximum")
    counts = snapshot.metadata["restriction_mapping_counts"]
    assert counts["outside_shift_scope"] == int(cause != "zero_maximum")
    assert counts["mapped_rows"] == int(cause == "zero_maximum")
    assert not any("RESTR" in issue for issue in snapshot.unresolved)
    assert any("Stammdatenreferenz fehlt" in issue for issue in snapshot.unresolved) == (
        cause in ("missing_demand_shift", "missing_workplace")
    )
    assert any("Zeitfenster fehlt" in issue for issue in snapshot.unresolved) == (
        cause == "missing_window"
    )
    if cause == "zero_maximum":
        assert snapshot.demands[0].maximum == 0
        assert snapshot.restrictions[0].level == 2
        assert not snapshot.restrictions[0].approved
    assert all(not employee.approvals for employee in snapshot.employees)
    assert all(request.get_method() == "GET" for request in calls)
