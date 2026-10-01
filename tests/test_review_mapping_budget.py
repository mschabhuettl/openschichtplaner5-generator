"""SEC-R2-MAPPING-PARSE-BUDGET: real ASGI, synthetic stores, no worker.

Measure actual RequestValidationError construction as well as its public report;
response cropping alone must not make these regressions pass.
"""
from collections.abc import Mapping
import json
import time

from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, ValidationError
import pytest

from sp5generator.demo import make_demo
from sp5generator.models import Snapshot
from sp5generator.security_limits import bounded_planning_records
from sp5generator.webapp import PlanRequest, ReplacementRequest, create_app

PLAN_ROUTES = [
    '/api/validate', '/api/approval-leverage', '/api/replacement',
    '/api/export/json', '/api/export/csv', '/api/export/xlsx',
]


def snapshot_payload():
    snapshot = make_demo(employees=3, days=1).model_dump(mode='json')
    snapshot['assignments'] = []
    snapshot['wishes'] = []
    return snapshot


def plan_payload(snapshot, route):
    payload = {'snapshot': snapshot, 'assignments': [{
        'employee_id': snapshot['employees'][0]['id'],
        'demand_id': snapshot['demands'][0]['id'], 'segments': [],
    }]}
    if route == '/api/replacement':
        payload.update(employee_id=snapshot['employees'][0]['id'],
                       absent_from=snapshot['period_start'], absent_until=snapshot['period_end'])
    return payload


@pytest.fixture
def exchange(tmp_path, record_property):
    app = create_app(str(tmp_path), start_worker=False)
    real_handler = app.exception_handlers[RequestValidationError]
    observed = []

    async def measured_handler(request, exc):
        errors = exc.errors()
        observed.append({
            'actual_schema_errors': len(errors),
            'size_limit_errors': sum('[size_limit]' in error['msg'] for error in errors),
        })
        return await real_handler(request, exc)

    app.add_exception_handler(RequestValidationError, measured_handler)
    with TestClient(app) as client:
        def send(route, payload, case, method='POST'):
            observed.clear()
            raw = json.dumps(payload, separators=(',', ':')).encode('utf-8')
            assert len(raw) < 16 * 1024 * 1024
            started = time.monotonic()
            response = client.request(method, route, content=raw,
                                      headers={'content-type': 'application/json'})
            report = response.json() if response.headers.get('content-type') == 'application/json' else {}
            measurement = {
                'case': case, 'route': route, 'method': method,
                'request_bytes': len(raw), 'response_bytes': len(response.content),
                'status': response.status_code, 'seconds': time.monotonic() - started,
                'fields_total': report.get('fields_total'), 'fields_omitted': report.get('fields_omitted'),
                **(observed[0] if observed else {'actual_schema_errors': 0, 'size_limit_errors': 0}),
            }
            record_property('measurement', json.dumps(measurement))
            print('MEASUREMENT ' + json.dumps(measurement))
            return response, measurement

        yield send
        # The tests do not submit jobs or deliberately save valid snapshots.
        assert client.get('/api/snapshots').json() == []
        assert client.get('/api/jobs').json() == []


def assert_preflight_rejected(response, measurement):
    assert response.status_code == 422
    assert measurement['actual_schema_errors'] == 1
    assert measurement['size_limit_errors'] == 1
    assert len(response.content) < 4096
    report = response.json()
    assert report['fields_total'] == 1
    assert report['fields_omitted'] == 0
    assert report['fields'] == [{'location': ['body'], 'type': 'value_error'}]


@pytest.mark.parametrize('route', PLAN_ROUTES)
def test_external_segment_mapping_rejected_before_schema_expansion(exchange, route):
    payload = plan_payload(snapshot_payload(), route)
    payload['assignments'][0]['segments'] = [{f'x{i}': None for i in range(50_001)}]
    response, measurement = exchange(route, payload, 'external-segment-map')
    assert measurement['request_bytes'] < 1024 * 1024
    assert_preflight_rejected(response, measurement)


@pytest.mark.parametrize('route', PLAN_ROUTES)
@pytest.mark.parametrize('case', ['request-extras', 'request-metadata'])
def test_whole_request_is_budgeted_not_just_selected_branches(exchange, route, case):
    payload = plan_payload(snapshot_payload(), route)
    values = {f'x{i}': None for i in range(50_001)}
    if case == 'request-extras':
        payload.update(values)
    else:
        # An ignored sibling field is not snapshot.metadata.
        payload['metadata'] = values
    response, measurement = exchange(route, payload, case)
    assert_preflight_rejected(response, measurement)


def test_inherited_request_field_cannot_bypass_preflight(exchange):
    route = '/api/replacement'
    payload = plan_payload(snapshot_payload(), route)
    payload['employee_id'] = {f'x{i}': None for i in range(50_001)}
    response, measurement = exchange(route, payload, 'inherited-request-field')
    assert_preflight_rejected(response, measurement)


@pytest.mark.parametrize('method,route', [
    ('POST', '/api/readiness'), ('POST', '/api/snapshots/check'), ('PUT', '/api/snapshots'),
])
@pytest.mark.parametrize('case', ['snapshot-extras', 'typed-map', 'snapshot-segment-map'])
def test_snapshot_mapping_rejected_before_schema_expansion(exchange, case, method, route):
    payload = snapshot_payload()
    values = {f'x{i}': None for i in range(50_001)}
    if case == 'snapshot-extras':
        payload.update(values)
    elif case == 'typed-map':
        payload['software_versions'] = values
    else:
        payload['shifts'][0]['segments'] = [values]
    response, measurement = exchange(route, payload, case, method=method)
    assert measurement['request_bytes'] < 1024 * 1024
    assert_preflight_rejected(response, measurement)


@pytest.mark.parametrize('case', [
    'mixed-map-list', 'shared-branches', 'assignment-metadata',
    'employee-metadata', 'nested-snapshot-metadata', 'malformed-snapshot-list',
])
def test_nested_shapes_cannot_reset_budget_or_inherit_metadata_exemption(exchange, case):
    payload = plan_payload(snapshot_payload(), '/api/validate')
    if case == 'mixed-map-list':
        payload['assignments'][0]['segments'] = [{'x': [None, None]} for _ in range(13_000)]
    elif case == 'shared-branches':
        # Each branch is under the ceiling, but the whole request is over it.
        payload['snapshot']['software_versions'] = {f'v{i}': '1' for i in range(25_001)}
        payload['assignments'][0]['segments'] = [{f'x{i}': None for i in range(25_001)}]
    else:
        values = {f'x{i}': None for i in range(50_001)}
        if case == 'assignment-metadata':
            payload['assignments'][0]['metadata'] = values
        elif case == 'employee-metadata':
            payload['snapshot']['employees'][0]['metadata'] = values
        elif case == 'nested-snapshot-metadata':
            payload['unknown'] = {'snapshot': {'metadata': values}}
        else:
            payload['snapshot'] = [{'metadata': values}]
    response, measurement = exchange('/api/validate', payload, case)
    assert_preflight_rejected(response, measurement)


def json_units(value, *, metadata_path, path=()):
    """Independent recursive oracle for finite JSON fixtures, not production code."""
    if path == metadata_path:
        return 1
    if isinstance(value, dict):
        return 1 + sum(json_units(child, metadata_path=metadata_path, path=(*path, key))
                       for key, child in value.items())
    if isinstance(value, list):
        return 1 + sum(json_units(child, metadata_path=metadata_path, path=(*path, index))
                       for index, child in enumerate(value))
    return 1


@pytest.mark.parametrize('route', ['/api/readiness', *PLAN_ROUTES])
def test_exact_budget_valid_payload_then_one_more_unit_is_rejected(exchange, route):
    snapshot = snapshot_payload()
    snapshot['software_versions'] = {}
    payload = snapshot if route == '/api/readiness' else plan_payload(snapshot, route)
    if route != '/api/readiness':
        # The old raw-only acceptance promise omitted Assignment.fixed. Under
        # the two-stage contract the positive boundary must fit after defaults.
        cls = ReplacementRequest if route == '/api/replacement' else PlanRequest
        payload = cls.model_validate(payload).model_dump(mode='json')
        snapshot = payload['snapshot']
    metadata_path = ('metadata',) if route == '/api/readiness' else ('snapshot', 'metadata')
    base_units = json_units(payload, metadata_path=metadata_path)
    snapshot['software_versions'] = {f'v{i}': '1' for i in range(50_000 - base_units)}
    assert json_units(payload, metadata_path=metadata_path) == 50_000
    response, measurement = exchange(route, payload, 'exact-50000-valid-units')
    assert response.status_code == 200, response.text[:1000]
    assert measurement['actual_schema_errors'] == 0
    if route == '/api/readiness':
        assert response.json()['ready']
    elif route == '/api/validate':
        assert response.json()['valid']
    snapshot['software_versions']['one-more'] = '1'
    assert json_units(payload, metadata_path=metadata_path) == 50_001
    response, measurement = exchange(route, payload, '50001-valid-units')
    assert_preflight_rejected(response, measurement)


@pytest.mark.parametrize('route', PLAN_ROUTES)
def test_raw_exact_budget_does_not_promise_normalized_acceptance(exchange, route):
    # Preserve the formerly accepted raw shape as a negative capacity oracle,
    # paired with the exact normalized positive boundary above. Historical RED
    # output is retained; neither stage's ceiling is raised or combined.
    snapshot = snapshot_payload()
    snapshot['software_versions'] = {}
    payload = plan_payload(snapshot, route)
    base_units = json_units(payload, metadata_path=('snapshot', 'metadata'))
    snapshot['software_versions'] = {f'v{i}': '1' for i in range(50_000 - base_units)}
    assert json_units(payload, metadata_path=('snapshot', 'metadata')) == 50_000
    response, measurement = exchange(route, payload, 'raw-50000-normalized-50001')
    assert response.status_code == 422
    assert measurement['actual_schema_errors'] == measurement['size_limit_errors'] == 1
    assert len(response.content) < 4096


@pytest.mark.parametrize('route', ['/api/readiness', '/api/snapshots/check', *PLAN_ROUTES])
def test_only_real_snapshot_metadata_is_exempt_and_ids_remain_exact(exchange, route):
    snapshot = snapshot_payload()
    employee_id = ' ' + '💡' * 198 + ' '
    snapshot['employees'][0]['id'] = employee_id
    custom = {'records': [{f'x{i}': None for i in range(50_001)}],
              'metadata': [None] * 50_001}
    snapshot['metadata']['custom'] = custom
    direct = route in {'/api/readiness', '/api/snapshots/check'}
    payload = snapshot if direct else plan_payload(snapshot, route)
    response, measurement = exchange(route, payload, 'metadata-and-exact-id-control')
    assert response.status_code == 200, response.text[:1000]
    assert measurement['actual_schema_errors'] == 0
    if route == '/api/snapshots/check':
        assert response.json()['metadata']['custom'] == custom
        assert response.json()['employees'][0]['id'] == employee_id
    elif route == '/api/export/json':
        assert response.json()['assignments'][0]['employee_id'] == employee_id
    elif route == '/api/readiness':
        assert response.json()['ready']
    elif route == '/api/validate':
        assert response.json()['valid']


@pytest.mark.parametrize('case', ['unknown-fields', 'typed-map', 'not-metadata'])
def test_small_schema_failures_are_not_replaced_by_budget_errors(exchange, case):
    payload = snapshot_payload()
    if case == 'unknown-fields':
        payload['shifts'][0]['segments'] = [{'x': None, 'y': None}]
        locations = [['body', 'shifts', 0, 'segments', 0, key] for key in ('start', 'end', 'x', 'y')]
        types = ['missing', 'missing', 'extra_forbidden', 'extra_forbidden']
    elif case == 'typed-map':
        payload['software_versions'] = {'x': None, 'y': None}
        locations = [['body', 'software_versions', key] for key in ('x', 'y')]
        types = ['string_type', 'string_type']
    else:
        payload['employees'][0]['metadata'] = {'x': None}
        locations = [['body', 'employees', 0, 'metadata']]
        types = ['extra_forbidden']
    response, measurement = exchange('/api/readiness', payload, 'small-' + case)
    assert response.status_code == 422
    assert measurement['actual_schema_errors'] == len(types)
    assert measurement['size_limit_errors'] == 0
    assert response.json()['fields'] == [
        {'location': location, 'type': kind} for location, kind in zip(locations, types)
    ]


def test_realistic_valid_project_is_accepted_after_budget_failure(exchange):
    invalid = snapshot_payload()
    invalid['software_versions'] = {f'x{i}': None for i in range(50_001)}
    assert_preflight_rejected(*exchange('/api/readiness', invalid, 'before-positive-control'))
    snapshot = make_demo(employees=200, days=14).model_dump(mode='json')
    units = json_units(snapshot, metadata_path=('metadata',))
    assert units < 50_000
    response, measurement = exchange('/api/readiness', snapshot, f'valid-200-people-14-days-{units}-units')
    assert response.status_code == 200
    assert response.json()['ready']
    assert measurement['actual_schema_errors'] == 0


@pytest.mark.parametrize('payload,is_request,units', [
    ({}, False, 1), ([], False, 1), (None, False, 1),
    ({'a': None}, False, 2), ({'a': {}}, False, 2), ({'a': []}, False, 2),
    ({'a': [None, {}, []]}, False, 5), ([{}, [], (None,)], False, 5),
    ({'metadata': {'not': ['charged']}}, False, 2),
    ({'a': {'metadata': {'x': None}}}, False, 4),
    ({'snapshot': {'metadata': {'x': None}}}, True, 3),
    ({'snapshot': {'metadata': {'x': None}}}, False, 4),
    ({'snapshot': [{'metadata': {'x': None}}]}, True, 5),
    ({'metadata': {'x': None}, 'snapshot': {'metadata': {'x': None}}}, True, 5),
])
def test_unit_semantics_charge_each_entry_once(monkeypatch, payload, is_request, units):
    monkeypatch.setattr('sp5generator.security_limits.MAX_PLANNING_PARSE_UNITS', units)
    assert bounded_planning_records(payload, request=is_request) is payload
    monkeypatch.setattr('sp5generator.security_limits.MAX_PLANNING_PARSE_UNITS', units - 1)
    with pytest.raises(ValueError, match=r'\[size_limit\]'):
        bounded_planning_records(payload, request=is_request)


class MeteredMapping(Mapping):
    """Lazy mapping: fail if the preflight materializes it or reads past budget."""
    def __init__(self):
        self.reads = 0

    def __len__(self):
        raise AssertionError('The preflight must not request an unbounded copy/length hint')

    def __iter__(self):
        for index in range(100_000):
            yield f'x{index}'

    def __getitem__(self, key):
        self.reads += 1
        assert self.reads <= 50_000, 'Traversal continued after its first excess unit'
        return None


def test_mapping_stops_at_first_excess_unit_without_copying():
    value = MeteredMapping()
    with pytest.raises(ValueError, match=r'\[size_limit\]'):
        bounded_planning_records(value)
    # One root unit + 50,000 fetched entries => reject unit 50,001.
    assert value.reads == 50_000


def test_shared_containers_are_counted_per_occurrence(monkeypatch):
    shared = {'a': None}
    value = {'x': shared, 'y': shared}
    monkeypatch.setattr('sp5generator.security_limits.MAX_PLANNING_PARSE_UNITS', 5)
    assert bounded_planning_records(value) is value
    monkeypatch.setattr('sp5generator.security_limits.MAX_PLANNING_PARSE_UNITS', 4)
    with pytest.raises(ValueError, match=r'\[size_limit\]'):
        bounded_planning_records(value)
    assert value['x'] is shared and value['y'] is shared


@pytest.mark.parametrize('shape', ['deep', 'cycle'])
def test_iterative_walk_is_bounded_without_python_recursion(shape):
    value = []
    if shape == 'cycle':
        value.append(value)
    else:
        for _ in range(50_001):
            value = {'a': [value]}
    with pytest.raises(ValueError, match=r'\[size_limit\]'):
        bounded_planning_records(value)


@pytest.mark.parametrize('is_request', [False, True])
def test_parsed_models_are_walked_without_dumping(monkeypatch, is_request):
    snapshot = make_demo(employees=3, days=1)
    snapshot.metadata['custom'] = MeteredMapping()
    value = PlanRequest(snapshot=snapshot, assignments=[]) if is_request else snapshot

    def no_dump(*args, **kwargs):
        raise AssertionError('Parsing-budget preflight must not dump/copy models')

    monkeypatch.setattr(BaseModel, 'model_dump', no_dump)
    monkeypatch.setattr(BaseModel, 'model_dump_json', no_dump)
    assert bounded_planning_records(value, request=is_request) is value
    assert snapshot.metadata['custom'].reads == 0
    snapshot.software_versions = {f'x{i}': '1' for i in range(50_001)}
    with pytest.raises(ValueError, match=r'\[size_limit\]'):
        bounded_planning_records(value, request=is_request)
    if is_request:
        with pytest.raises(ValidationError, match=r'\[size_limit\]') as error:
            PlanRequest.model_validate({'snapshot': snapshot, 'assignments': []})
        assert error.value.error_count() == 1


def test_parsed_model_extras_and_nested_metadata_are_charged():
    class Extensible(BaseModel):
        model_config = ConfigDict(extra='allow')

    nested = Extensible.model_construct(metadata={f'x{i}': None for i in range(50_001)})
    assert nested.__pydantic_extra__ is not None
    assert 'metadata' in nested.__pydantic_extra__
    with pytest.raises(ValueError, match=r'\[size_limit\]'):
        bounded_planning_records({'employees': [nested]})


def test_snapshot_model_json_entry_uses_same_preflight():
    value = snapshot_payload()
    value['software_versions'] = {f'x{i}': None for i in range(50_001)}
    with pytest.raises(ValidationError, match=r'\[size_limit\]') as error:
        Snapshot.model_validate_json(json.dumps(value))
    assert error.value.error_count() == 1
