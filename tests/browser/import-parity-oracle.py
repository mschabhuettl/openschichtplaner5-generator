"""Independent strict typed/raw-wire oracle; no source imports or normalization."""
import copy
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import uuid
from collections import Counter


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result, ('duplicate JSON key', key)
        result[key] = value
    return result


def parse(text):
    return json.loads(text, object_pairs_hook=unique_object, parse_constant=lambda x: (_ for _ in ()).throw(AssertionError(x)))


def equal(a, b, path='$'):
    assert type(a) is type(b), (path, type(a).__name__, type(b).__name__)
    if isinstance(a, dict):
        assert a.keys() == b.keys(), (path, a.keys() ^ b.keys())
        for key in a:
            equal(a[key], b[key], path + '.' + key)
    elif isinstance(a, list):
        assert len(a) == len(b), (path, len(a), len(b))
        for i, (x, y) in enumerate(zip(a, b)):
            equal(x, y, f'{path}[{i}]')
    elif isinstance(a, float):
        assert math.isfinite(a) and a.hex() == b.hex(), (path, a.hex(), b.hex())
    else:
        assert a == b, (path, a, b)


def generated(snapshot, result, source_type):
    prefix = 'sp5:api-import:' if source_type == 'api' else 'sp5:import:'
    identifier = snapshot['id']
    assert re.fullmatch(re.escape(prefix) + r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}', identifier), identifier
    value = uuid.UUID(identifier.removeprefix(prefix))
    assert value.version == 4 and value.variant == uuid.RFC_4122
    stamp = snapshot['created_at']
    assert re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{6})?Z', stamp), stamp
    when = dt.datetime.fromisoformat(stamp)
    assert when.utcoffset() == dt.timedelta(0)
    delta = when - dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
    micros = (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds
    assert result['beforeMs'] * 1000 <= micros < (result['afterMs'] + 1) * 1000, (stamp, result['beforeMs'], result['afterMs'])
    return {'id': identifier, 'created_at': stamp, 'uuid_version': value.version, 'utc': True, 'microseconds': micros, 'lower_inclusive_us': result['beforeMs'] * 1000, 'upper_exclusive_us': (result['afterMs'] + 1) * 1000}


def without_generated(snapshot):
    out = copy.deepcopy(snapshot)
    del out['id']
    del out['created_at']
    return out


def categories(value):
    counts = Counter([type(value).__name__])
    if isinstance(value, dict):
        for child in value.values():
            counts.update(categories(child))
    elif isinstance(value, list):
        for child in value:
            counts.update(categories(child))
    return counts


source = Path(sys.argv[1])
observed = parse(source.read_text())
preset, manual = observed['preset'], observed['manual']
assert preset['requestText'].encode() == manual['requestText'].encode()
request = parse(preset['requestText'])
assert request['team_ids'] == ['2'] and request['period_start'] == '2026-02-01' and request['period_end'] == '2026-02-28'
stages = {}
validation = []
for name, result in [('preset', preset), ('manual', manual)]:
    stages[name] = {stage: parse(result[field]) for stage, field in [('remote', 'remoteText'), ('admission_request', 'checkRequestText'), ('admission_response', 'checkResponseText'), ('canonical', 'canonicalText')]}
    reference = stages[name]['remote']['snapshot']
    for stage, content in stages[name].items():
        snapshot = content['snapshot'] if stage == 'remote' else content
        details = generated(snapshot, result, observed['sourceType'])
        assert snapshot['id'] == reference['id'] and snapshot['created_at'] == reference['created_at'], (name, stage, 'generated fields changed during admission')
        validation.append({'run': name, 'stage': stage, **details})
    equal(stages[name]['admission_response'], stages[name]['canonical'])
    equal(stages[name]['admission_request'], stages[name]['admission_response'])
    canonical = stages[name]['canonical']
    assert [e['id'] for e in canonical['employees']] == ['sp5:employee:101', 'sp5:employee:103']
    assert all(p['confirmed'] is False for p in canonical['profiles'])
    assert all(e['approvals'] == [] and e['qualifications'] == [] for e in canonical['employees'])
assert stages['preset']['canonical']['id'] != stages['manual']['canonical']['id']
compared = {}
for stage in stages['preset']:
    left, right = copy.deepcopy(stages['preset'][stage]), copy.deepcopy(stages['manual'][stage])
    if stage == 'remote':
        left['snapshot'], right['snapshot'] = without_generated(left['snapshot']), without_generated(right['snapshot'])
    else:
        left, right = without_generated(left), without_generated(right)
    equal(left, right)
    compared[stage] = {'complete_typed_structure_equal': True, 'categories': dict(categories(left))}
# Negative oracle controls are synthetic mutations, not product defects.
negative_controls = []
for label, left, right in [('integer-versus-float', {'x': 1}, {'x': 1.0}), ('boolean-versus-integer', {'x': True}, {'x': 1}), ('negative-zero', {'x': 0.0}, {'x': -0.0}), ('nested-identifier', {'metadata': {'id': 'a'}}, {'metadata': {'id': 'b'}}), ('missing-field', {'x': None}, {})]:
    try:
        equal(left, right)
    except AssertionError:
        negative_controls.append(label)
    else:
        raise AssertionError(('oracle accepted mutation', label))
canonical = stages['preset']['canonical']
report = {'status': 'PASS', 'source_type': observed['sourceType'], 'request_bytes_equal': True, 'request_sha256': hashlib.sha256(preset['requestText'].encode()).hexdigest(), 'wire_evidence_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'generated_validation': validation, 'stage_comparison': compared, 'only_excluded_paths': ['remote.snapshot.id', 'remote.snapshot.created_at', 'admission_request.id', 'admission_request.created_at', 'admission_response.id', 'admission_response.created_at', 'canonical.id', 'canonical.created_at'], 'within_import_identity_and_timestamp_preserved': True, 'admission_request_response_canonical_typed_equal': True, 'negative_oracle_controls_rejected': negative_controls, 'totals': {'employees': len(canonical['employees']), 'target_minutes': sum(e['target_minutes'] for e in canonical['employees']), 'credit_minutes': sum(e['credit_minutes'] for e in canonical['employees']), 'balance_minutes': sum(e['balance_minutes'] for e in canonical['employees']), 'approvals': sum(len(e['approvals']) for e in canonical['employees']), 'qualifications': sum(len(e['qualifications']) for e in canonical['employees']), 'shifts': len(canonical['shifts']), 'demands': len(canonical['demands']), 'positions': len(canonical['positions']), 'history_rows': len(canonical['metadata'].get('history_matrix', []))}, 'no_implicit_save': observed['backendBefore'] == observed['backendAfter'] and all(x['status'] == 404 for x in observed['unpersistedIds'])}
print(json.dumps(report, ensure_ascii=False, indent=2))
