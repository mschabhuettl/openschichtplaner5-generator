"""Synthetic SEC-03/04 regressions; no listener or production state.

The process tests launch the real web lifespan, worker and calculation process.
A private process group and a Linux subreaper guarantee cleanup even on RED.
"""
import asyncio
import ctypes
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from sp5generator.demo import make_demo
from sp5generator.jobs import Store


def _alive(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except FileNotFoundError:
        return False


def _children(pid):
    try:
        return [int(p) for p in Path(f"/proc/{pid}/task/{pid}/children").read_text().split()]
    except FileNotFoundError:
        return []


def _wait(predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.02)
    return predicate()


def _locked(path):
    with open(str(path) + ".worker.lock", "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
    return False


@pytest.fixture
def process_tree(tmp_path):
    if sys.platform != "linux":
        pytest.skip("Real parent-death/subreaper integration requires Linux")
    libc = ctypes.CDLL(None)
    previous = ctypes.c_int()
    assert libc.prctl(37, ctypes.byref(previous), 0, 0, 0) == 0
    assert libc.prctl(36, 1, 0, 0, 0) == 0
    roots, tracked, logs = [], set(), []

    def start(mode, state):
        ready = tmp_path / f"ready-{len(roots)}.json"
        log = (tmp_path / f"process-{len(roots)}.log").open("w")
        logs.append(log)
        root = subprocess.Popen(
            [sys.executable, __file__, mode, str(state), str(ready)],
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )
        roots.append(root)
        assert _wait(lambda: ready.exists() or root.poll() is not None, 25)
        assert ready.exists(), f"Startup failed; see {log.name}"
        tracked.update(_children(root.pid))
        return root, json.loads(ready.read_text())

    try:
        yield start, tracked
    finally:
        # Kill only our newly-created process groups, then reap adopted orphans.
        for root in roots:
            tracked.update(_children(root.pid))
        for pid in tuple(tracked):
            tracked.update(_children(pid))
        for root in roots:
            try:
                os.killpg(root.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            root.wait(timeout=10)
            # Reap even helpers created after our first tree observation (e.g.
            # the CLI's resource tracker). All share this private process group.
            while True:
                try:
                    pid, _ = os.waitpid(-root.pid, 0)
                    tracked.add(pid)
                except ChildProcessError:
                    break
        for pid in tracked:
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass
        for log in logs:
            log.close()
        assert all(not _alive(pid) for pid in tracked)
        assert libc.prctl(36, previous.value, 0, 0, 0) == 0
        print(json.dumps({"cleanup_all_tracked_descendants_stopped": True,
                          "tracked_descendants": sorted(tracked)}))


@pytest.mark.parametrize("running", [False, True], ids=["idle", "calculation"])
def test_managed_worker_tree_dies_with_web_and_same_store_restarts(tmp_path, process_tree, running):
    start, tracked = process_tree
    state = tmp_path / "state"
    store = Store(state / "planning.sqlite3")
    web, ready = start("web-parent", state)
    worker = ready["worker_pid"]
    assert _alive(worker) and _locked(store.path)
    calculation = job = None
    if running:
        snapshot = store.save_snapshot(make_demo(employees=120, days=31), "local-user")
        job = store.submit(snapshot.id, "local-user", time_limit=30)
        children = _wait(lambda: _children(worker))
        assert children, "Real worker never spawned a calculation"
        tracked.update(children)
        calculation = children[0]
        assert _alive(calculation)
        assert store.get_job(job["id"], "local-user")["state"] == "running"
    web.kill()
    web.wait(timeout=5)
    assert web.returncode == -signal.SIGKILL
    assert _wait(lambda: not _alive(worker), 12), "Managed worker survived web SIGKILL"
    if calculation is not None:
        assert _wait(lambda: not _alive(calculation), 10), "Calculation survived the web process tree"
    assert not _locked(store.path), "Dead managed worker retained the store lock"
    restarted, replacement = start("web-parent", state)
    assert _alive(replacement["worker_pid"]) and _locked(store.path)
    if running:
        assert job is not None
        recovered = store.get_job(job["id"], "local-user")
        assert recovered["state"] == "failed"
        assert recovered["finished_at"] is not None
        assert recovered["result"] is None
    smoke = make_demo(employees=4, days=1)
    smoke.id = 'restart-smoke'
    smoke = store.save_snapshot(smoke, 'local-user')
    next_job = store.submit(smoke.id, 'local-user', time_limit=3)
    assert _wait(lambda: store.get_job(next_job['id'], 'local-user')['state'] == 'succeeded', 25)
    print(json.dumps({"case": "calculation" if running else "idle", "web_exitcode": web.returncode,
                      "worker_stopped": True, "calculation_pid": calculation,
                      "same_store_restart": True, "restart_real_job": "succeeded",
                      "restart_web_pid": restarted.pid}))


def test_standalone_cli_worker_survives_launcher_death(tmp_path, process_tree):
    start, tracked = process_tree
    store = Store(tmp_path / "independent.sqlite3")
    launcher, ready = start("cli-launcher", Path(store.path))
    worker = ready["worker_pid"]
    tracked.add(worker)
    assert _alive(worker) and _locked(store.path)
    launcher.kill()
    launcher.wait(timeout=5)
    snapshot = store.save_snapshot(make_demo(employees=4, days=1), "local-user")
    job = store.submit(snapshot.id, "local-user", time_limit=3)
    assert _wait(lambda: store.get_job(job["id"], "local-user")["state"] == "succeeded", 25)
    assert _alive(worker) and _locked(store.path)
    os.kill(worker, signal.SIGTERM)
    assert _wait(lambda: not _alive(worker), 12)
    assert not _locked(store.path)
    print(json.dumps({"standalone_cli_survived_launcher_death": True,
                      "subsequent_real_job": "succeeded", "graceful_lock_release": True}))


def test_overlong_identifier_amplification_is_rejected_without_echo(tmp_path):
    from fastapi.testclient import TestClient
    from sp5generator.webapp import create_app
    snapshot = make_demo(employees=3, days=1).model_dump(mode="json")
    snapshot["assignments"] = snapshot["wishes"] = []
    person = snapshot["employees"][0]
    person["id"] = "synthetic-" + "x" * 16384
    person["approvals"] = [
        {"function_id": "f0", "workplace_id": "w0", "valid_from": "2026-01-06", "valid_until": "2026-01-05"}
        for _ in range(256)
    ]
    raw = json.dumps(snapshot, separators=(",", ":")).encode()
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        response = client.post("/api/readiness", content=raw, headers={"content-type": "application/json"})
    print(json.dumps({"case": "original_amplification", "request_bytes": len(raw),
                      "response_bytes": len(response.content), "status": response.status_code}))
    assert response.status_code == 422
    assert len(response.content) < 16_384
    assert person["id"] not in response.text
    assert any(e["type"] == "string_too_long" for e in response.json()["fields"])


@pytest.mark.parametrize("model,field", [
    ("Employee", "id"), ("Employee", "team_ids"), ("Employee", "profile_ids"),
    ("Employee", "preferred_functions"), ("Qualification", "id"),
    ("Approval", "function_id"), ("Approval", "workplace_id"),
    ("RuleProfile", "id"), ("Position", "id"), ("Position", "function_id"),
    ("Position", "workplace_id"), ("Position", "qualification_ids"),
    ("Shift", "id"), ("Shift", "team_id"), ("BoundaryWork", "id"),
    ("BoundaryWork", "employee_id"), ("Demand", "id"), ("Demand", "shift_id"),
    ("Demand", "position_id"), ("Demand", "team_ids"), ("Demand", "alternative_group"),
    ("Assignment", "employee_id"), ("Assignment", "demand_id"),
    ("Restriction", "employee_id"), ("Restriction", "shift_id"),
    ("Wish", "employee_id"), ("Wish", "shift_id"), ("Snapshot", "id"),
    ("Result", "snapshot_id"),
])
def test_identity_boundary_rejects_not_truncates(model, field):
    from pydantic import TypeAdapter, ValidationError
    from sp5generator import models
    annotation = getattr(models, model).model_fields[field].rebuild_annotation()
    adapter = TypeAdapter(annotation)
    value = " " + "ä" * 198 + " "
    valid = [value] if field.endswith("s") else value
    invalid = [value + "x"] if field.endswith("s") else value + "x"
    assert adapter.validate_python(valid) == valid
    with pytest.raises(ValidationError, match="string_too_long"):
        adapter.validate_python(invalid)


@pytest.mark.parametrize("field", ["approvals", "qualifications", "availability", "unavailable",
                                   "team_ids", "profile_ids", "preferred_functions", "allowed_kinds"])
def test_repeated_employee_collections_rejected_before_diagnostics(tmp_path, monkeypatch, field):
    from fastapi.testclient import TestClient
    from sp5generator.webapp import create_app
    snapshot = make_demo(employees=3, days=1).model_dump(mode="json")
    person = snapshot["employees"][0]
    records = {
        "qualifications": {"id": "q", "valid_from": "2026-01-01", "valid_until": "2026-02-01"},
        "unavailable": snapshot["shifts"][0]["segments"][0],
        "preferred_functions": "f0",
    }
    example = records[field] if field in records else person[field][0]
    person[field] = [example] * 1001
    reached = []
    monkeypatch.setattr("sp5generator.domain.input_diagnostics", lambda value: reached.append(True) or [])
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        response = client.post("/api/readiness", json=snapshot)
    assert response.status_code == 422
    assert not reached, "Oversized collection reached diagnostic expansion"
    assert len(response.content) < 16_384


@pytest.mark.parametrize("endpoint", ["/api/readiness", "/api/validate"])
def test_http_diagnostic_reports_bound_list_and_preserve_total(tmp_path, endpoint):
    from fastapi.testclient import TestClient
    from sp5generator.webapp import create_app
    snapshot = make_demo(employees=3, days=1).model_dump(mode="json")
    person = snapshot["employees"][0]
    person["id"] = "💡" * 200
    snapshot["assignments"] = snapshot["wishes"] = []
    person["approvals"] = [dict(person["approvals"][0], valid_from="2026-01-06", valid_until="2026-01-05")] * 256
    payload = snapshot if endpoint.endswith("readiness") else {"snapshot": snapshot, "assignments": []}
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        response = client.post(endpoint, json=payload)
    assert response.status_code == 200
    report = response.json()
    assert not report["ready" if endpoint.endswith("readiness") else "valid"]
    print(json.dumps({"case": endpoint, "response_bytes": len(response.content),
                      "returned_diagnostics": len(report["diagnostics"])}))
    assert len(response.content) <= 65_536
    assert len(report["diagnostics"]) <= 100
    assert report["diagnostics_total"] == 256
    assert report["diagnostics_omitted"] == 256 - len(report["diagnostics"])
    assert report["diagnostics_by_code"] == {"validity": 256}
    assert all(item["employee_id"] == person["id"] for item in report["diagnostics"])


def test_http_truncation_never_hides_late_hard_failure(tmp_path):
    from fastapi.testclient import TestClient
    from sp5generator.webapp import create_app
    snapshot = make_demo(employees=4, days=60).model_dump(mode="json")
    assignments = snapshot["assignments"][:1]
    snapshot["assignments"] = snapshot["wishes"] = []
    snapshot["profiles"][0]["max_period_minutes"] = 0
    payload = {"snapshot": snapshot, "assignments": assignments}
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        response = client.post("/api/validate", json=payload)
        assert client.post("/api/export/json", json=payload).status_code == 422
    report = response.json()
    assert response.status_code == 200
    assert not report["valid"] and not report["complete"]
    assert len(report["diagnostics"]) <= 100
    assert report["diagnostics_omitted"] > 0
    assert report["diagnostics_by_code"]["period_limit"] >= 1
    assert any(issue["code"] == "period_limit" for issue in report["diagnostics"])


@pytest.mark.parametrize("method,endpoint", [("post", "/api/snapshots/check"), ("put", "/api/snapshots")])
def test_http_structure_errors_are_size_bounded_without_saving(tmp_path, method, endpoint):
    from fastapi.testclient import TestClient
    from sp5generator.webapp import create_app
    snapshot = make_demo(employees=3, days=1).model_dump(mode="json")
    template = snapshot["shifts"][0]
    snapshot["shifts"] = [dict(template, id=f"{i:04}" + "x" * 196, segments=[]) for i in range(500)]
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        response = getattr(client, method)(endpoint, json=snapshot)
        assert client.get("/api/snapshots").json() == []
    assert response.status_code == 422
    assert len(response.content) <= 65_536
    assert "interval" in response.json()["detail"]


def test_http_schema_errors_have_bounded_fields_and_no_input_echo(tmp_path):
    from fastapi.testclient import TestClient
    from sp5generator.webapp import create_app
    snapshot = make_demo(employees=3, days=1).model_dump(mode="json")
    snapshot["employees"] = [{"name": "private-synthetic-marker"}] * 600
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        response = client.post("/api/readiness", json=snapshot)
    assert response.status_code == 422
    assert len(response.content) <= 65_536
    report = response.json()
    assert len(report["fields"]) <= 100
    assert report["fields_total"] > len(report["fields"])
    assert report["fields_omitted"] == report["fields_total"] - len(report["fields"])
    assert "private-synthetic-marker" not in response.text


def test_http_schema_error_does_not_echo_overlong_extra_field_name(tmp_path):
    from fastapi.testclient import TestClient
    from sp5generator.webapp import create_app
    snapshot = make_demo(employees=3, days=1).model_dump(mode="json")
    field = "private-field-" + "💡" * 20_000
    snapshot[field] = None
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        response = client.post("/api/readiness", json=snapshot)
    assert response.status_code == 422
    assert len(response.content) <= 65_536
    assert "private-field-" not in response.text


def test_import_validation_error_uses_same_safe_http_handler(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from sp5generator.models import Snapshot
    from sp5generator.webapp import create_app
    snapshot = make_demo(employees=3, days=1).model_dump(mode="json")
    snapshot["employees"] = [{"name": "private-import-marker"}] * 600

    def invalid_import(**kwargs):
        return Snapshot.model_validate(snapshot)

    monkeypatch.setattr("sp5generator.api_adapter.import_api", invalid_import)
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        response = client.post("/api/remote-import", json={
            "period_start": "2026-01-01", "period_end": "2026-01-31", "timezone": "UTC",
        })
    assert response.status_code == 422
    assert len(response.content) <= 65_536
    assert "private-import-marker" not in response.text
    assert response.json()["fields_omitted"] > 0


def test_oversized_top_level_collection_rejected_before_item_errors(tmp_path):
    from fastapi.testclient import TestClient
    from sp5generator.webapp import create_app
    snapshot = make_demo(employees=3, days=1).model_dump(mode="json")
    snapshot["employees"] = [{}] * 1001
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        response = client.post("/api/readiness", json=snapshot)
    assert response.status_code == 422
    assert response.json()["fields_total"] == 1
    assert response.json()["fields"][0]["location"] == ["body", "employees"]


@pytest.mark.parametrize("endpoint", ["/api/readiness", "/api/validate", "/api/snapshots/check", "/api/export/json"])
def test_diagnostic_construction_budget_fails_closed_and_resets(tmp_path, monkeypatch, endpoint):
    from fastapi.testclient import TestClient
    from sp5generator.models import Diagnostic
    from sp5generator.webapp import create_app
    snapshot = make_demo(employees=10, days=1).model_dump(mode="json")
    snapshot["assignments"] = snapshot["wishes"] = []
    for index, person in enumerate(snapshot["employees"]):
        person["id"] = f"{index:03}" + "x" * 197
        person["approvals"] = [dict(person["approvals"][0], valid_from="2026-01-06", valid_until="2026-01-05")] * 300
    generated = []

    def counted_diagnostic(**kwargs):
        generated.append(True)
        return Diagnostic(**kwargs)

    monkeypatch.setattr("sp5generator.domain.Diagnostic", counted_diagnostic)
    payload = {"snapshot": snapshot, "assignments": []} if endpoint in {"/api/validate", "/api/export/json"} else snapshot
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        response = client.post(endpoint, json=payload)
        assert client.get("/api/snapshots").json() == []
        assert client.post("/api/readiness", json=make_demo(employees=3, days=1).model_dump(mode="json")).json()["ready"]
    assert response.status_code == 422
    assert response.json()["code"] == "diagnostic_limit"
    assert len(response.content) <= 65_536
    assert len(generated) < 3000, "Diagnostic budget only cropped after constructing every error"


@pytest.mark.parametrize("field,limit", [("positions", 2000), ("shifts", 10000), ("demands", 20000),
                                        ("profiles", 1000), ("assignments", 5000), ("boundary_work", 5000),
                                        ("restrictions", 20000), ("wishes", 20000), ("unresolved", 1000)])
def test_remaining_top_level_collections_rejected_before_item_errors(tmp_path, field, limit):
    from fastapi.testclient import TestClient
    from sp5generator.webapp import create_app
    snapshot = make_demo(employees=3, days=1).model_dump(mode="json")
    snapshot[field] = [{}] * (limit + 1)
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        response = client.post("/api/readiness", json=snapshot)
    assert response.status_code == 422
    assert response.json()["fields_total"] == 1
    assert response.json()["fields"][0]["location"] == ["body", field]


def test_nested_parse_budget_precedes_expanding_missing_field_errors(tmp_path):
    from fastapi.testclient import TestClient
    from sp5generator.webapp import create_app
    snapshot = make_demo(employees=100, days=1).model_dump(mode="json")
    for person in snapshot["employees"]:
        person["approvals"] = [{}] * 600
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        response = client.post("/api/readiness", json=snapshot)
    assert response.status_code == 422
    assert response.json()["fields_total"] == 1
    assert len(response.content) < 4096


def test_external_assignment_collection_is_bounded_before_item_errors(tmp_path):
    from fastapi.testclient import TestClient
    from sp5generator.webapp import create_app
    payload = {"snapshot": make_demo(employees=3, days=1).model_dump(mode="json"), "assignments": [{}] * 5001}
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        response = client.post("/api/validate", json=payload)
    assert response.status_code == 422
    assert response.json()["fields_total"] == 1
    assert response.json()["fields"][0]["location"] == ["body", "assignments"]


@pytest.mark.parametrize("endpoint", [
    "/api/validate", "/api/approval-leverage", "/api/replacement",
    "/api/export/json", "/api/export/csv", "/api/export/xlsx",
])
@pytest.mark.parametrize("layout", ["single", "multiple", "snapshot-and-external", "empty-containers"])
def test_http_external_assignment_parse_budget_precedes_item_errors(tmp_path, endpoint, layout):
    """Sub-MiB bodies must not expand tens of thousands of schema errors."""
    from fastapi.testclient import TestClient
    from sp5generator.webapp import create_app

    snapshot = make_demo(employees=3, days=1).model_dump(mode="json")
    snapshot["assignments"] = snapshot["wishes"] = []
    assignment = {
        "employee_id": snapshot["employees"][0]["id"],
        "demand_id": snapshot["demands"][0]["id"],
    }
    if layout == "single":
        assignments = [dict(assignment, segments=[None] * 50_001)]
    elif layout == "empty-containers":
        assignments = [dict(assignment, segments=[[] for _ in range(50_001)])]
    else:
        assignments = [dict(assignment, segments=[None] * 25_001) for _ in range(2)]
        if layout == "snapshot-and-external":
            snapshot["assignments"] = [assignments.pop()]
    payload = {"snapshot": snapshot, "assignments": assignments}
    if endpoint == "/api/replacement":
        payload.update(employee_id=assignment["employee_id"],
                       absent_from=snapshot["period_start"], absent_until=snapshot["period_end"])
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    # The real 16-MiB middleware remains enabled: rejection must come from the
    # aggregate parse budget, not Content-Length or response-list cropping.
    assert len(raw) < 1024 * 1024 < 16 * 1024 * 1024
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        response = client.post(endpoint, content=raw, headers={"content-type": "application/json"})
        assert client.get("/api/snapshots").json() == []
        assert client.get("/api/jobs").json() == []
    assert response.status_code == 422
    report = response.json()
    print(json.dumps({"case": "external_assignment_parse_budget", "endpoint": endpoint,
                      "layout": layout, "request_bytes": len(raw),
                      "response_bytes": len(response.content), "fields_total": report["fields_total"]}))
    assert report["fields_total"] == 1
    assert report["fields_omitted"] == 0
    assert report["fields"] == [{"location": ["body"], "type": "value_error"}]
    assert len(response.content) < 4096


@pytest.mark.parametrize("endpoint", ["/api/readiness", "/api/validate"])
@pytest.mark.parametrize("overflow", ["characters", "utf8", "remaining-bytes", "item-limit"])
def test_http_diagnostic_sample_skips_unfittable_records(tmp_path, endpoint, overflow):
    from fastapi.testclient import TestClient
    from sp5generator.webapp import create_app

    snapshot = make_demo(employees=3, days=1).model_dump(mode="json")
    snapshot["assignments"] = snapshot["wishes"] = []
    small = "small later diagnostic"
    expected = [small]
    if overflow == "characters":
        snapshot["unresolved"] = ["x" * 49_153, small]
    elif overflow == "utf8":
        snapshot["unresolved"] = ["💡" * 13_000, small]
    elif overflow == "remaining-bytes":
        snapshot["unresolved"] = ["a" * 30_000, "b" * 25_000, small]
        expected = [snapshot["unresolved"][0], small]
    else:
        snapshot["unresolved"] = ["x" * 49_153] + [small] * 101
        expected = [small] * 100
    payload = snapshot if endpoint == "/api/readiness" else {"snapshot": snapshot, "assignments": []}
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    assert len(raw) < 1024 * 1024
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        response = client.post(endpoint, content=raw, headers={"content-type": "application/json"})
        # Omission never turns a bad draft into a permitted export.
        for format in ("json", "csv", "xlsx"):
            assert client.post(f"/api/export/{format}", json={
                "snapshot": snapshot, "assignments": [],
            }).status_code == 422
    assert response.status_code == 200
    report = response.json()
    assert not report["ready" if endpoint == "/api/readiness" else "valid"]
    if endpoint == "/api/validate":
        assert not report["complete"]
    total = len(snapshot["unresolved"])
    print(json.dumps({"case": "diagnostic_sampling", "endpoint": endpoint, "overflow": overflow,
                      "request_bytes": len(raw), "response_bytes": len(response.content),
                      "shown": len(report["diagnostics"]), "total": report["diagnostics_total"],
                      "omitted": report["diagnostics_omitted"]}))
    assert [issue["message"] for issue in report["diagnostics"]] == expected
    assert report["diagnostics_total"] == total
    assert report["diagnostics_omitted"] == total - len(expected)
    assert report["diagnostics_by_code"] == {"unresolved": total}
    assert len(report["diagnostics"]) <= 100
    encoded = json.dumps(report["diagnostics"], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    assert len(encoded) <= 48 * 1024
    assert len(response.content) <= 65_536


@pytest.mark.parametrize("endpoint", [
    "/api/validate", "/api/approval-leverage", "/api/replacement",
    "/api/export/json", "/api/export/csv", "/api/export/xlsx",
])
def test_http_plan_budget_controls_keep_metadata_and_small_errors(tmp_path, endpoint):
    """Positive controls: metadata is exempt; ordinary schema errors stay exact."""
    from fastapi.testclient import TestClient
    from sp5generator.webapp import create_app

    snapshot = make_demo(employees=3, days=1).model_dump(mode="json")
    snapshot["assignments"] = snapshot["wishes"] = []
    employee_id = " " + "💡" * 198 + " "
    snapshot["employees"][0]["id"] = employee_id
    snapshot["metadata"]["custom"] = {"records": [None] * 50_001}
    assignment = {"employee_id": employee_id, "demand_id": snapshot["demands"][0]["id"],
                  "segments": [None, None]}
    payload = {"snapshot": snapshot, "assignments": [assignment]}
    if endpoint == "/api/replacement":
        payload.update(employee_id=employee_id, absent_from=snapshot["period_start"],
                       absent_until=snapshot["period_end"])
    with TestClient(create_app(str(tmp_path), start_worker=False)) as client:
        invalid = client.post(endpoint, json=payload)
        assert invalid.status_code == 422
        assert invalid.json()["fields_total"] == 2
        assert invalid.json()["fields_omitted"] == 0
        assert [field["location"] for field in invalid.json()["fields"]] == [
            ["body", "assignments", 0, "segments", i] for i in range(2)
        ]
        assignment["segments"] = []
        valid = client.post(endpoint, json=payload)
        assert valid.status_code == 200, valid.text[:1000]
        if endpoint == "/api/validate":
            assert valid.json()["valid"] and not valid.json()["complete"]
        if endpoint == "/api/export/json":
            assert valid.json()["assignments"][0]["employee_id"] == employee_id
        assert client.get("/api/snapshots").json() == []
    print(json.dumps({"case": "plan_budget_positive_control", "endpoint": endpoint,
                      "metadata_records": 50_001, "ordinary_fields_total": 2,
                      "subsequent_status": valid.status_code}))


async def _web_parent(state, ready):
    from sp5generator.webapp import create_app
    app = create_app(str(state), start_worker=True)
    async with app.router.lifespan_context(app):
        ready.write_text(json.dumps({"worker_pid": app.state.worker.pid}))
        await asyncio.Event().wait()


def _cli_launcher(store, ready):
    worker = subprocess.Popen([sys.executable, "-m", "sp5generator.cli", "worker", "--store", str(store)])
    assert _wait(lambda: _locked(store) or worker.poll() is not None)
    assert worker.poll() is None
    ready.write_text(json.dumps({"worker_pid": worker.pid}))
    worker.wait()


if __name__ == "__main__":
    mode, state, ready = sys.argv[1:]
    if mode == "web-parent":
        asyncio.run(_web_parent(Path(state), Path(ready)))
    elif mode == "cli-launcher":
        _cli_launcher(Path(state), Path(ready))
    else:
        raise ValueError("Unknown synthetic process test mode")
