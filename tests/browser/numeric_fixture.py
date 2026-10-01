"""Disposable real app and Python/SQLite oracle for numeric browser tests."""
import json
import os
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from json_numeric_oracle import signature  # noqa: E402


def fixture():
    return {
        'id': 'numeric-source', 'revision': '0', 'source': 'synthetic',
        'created_at': '2026-01-01T00:00:00Z', 'rule_version': 'numeric-synthetic',
        'timezone': 'UTC', 'period_start': '2026-01-05', 'period_end': '2026-01-05',
        'context_start': '2025-12-22', 'context_end': '2026-01-19', 'context_complete': True,
        'employees': [{'id': 'p', 'name': 'Synthetic Ada', 'target_minutes': 60,
                       'employment_start': '2025-12-22', 'employment_end': '2026-01-19',
                       'team_ids': ['t'], 'profile_ids': ['r'],
                       'approvals': [{'function_id': 'f', 'workplace_id': 'w',
                                      'valid_from': '2025-12-22', 'valid_until': '2026-01-19'}]}],
        'positions': [{'id': 'pos', 'name': 'Synthetic role', 'function_id': 'f',
                       'workplace_id': 'w', 'qualifications_required': False}],
        'profiles': [{'id': 'r', 'valid_from': '2025-12-22', 'valid_until': '2026-01-19',
                      'min_rest_minutes': 0, 'confirmed': True}],
        'shifts': [{'id': 's', 'name': 'Synthetic shift', 'kind': 'day', 'team_id': 't',
                    'segments': [{'start': '2026-01-05T08:00:00Z', 'end': '2026-01-05T09:00:00Z'}],
                    'paid_minutes': 60}],
        'demands': [{'id': 'd', 'shift_id': 's', 'position_id': 'pos', 'minimum': 1, 'maximum': 1}],
        'metadata': {'project_name': 'Numeric synthetic', 'opaque': {
            'integer': 9007199254740993, 'large': 10**400,
            'float': 1.0000000000000001e18, 'rows': [-0.0, 1.0, 1e20, 0.1],
            'unicode': 'ä💡𐐀', 'numeric_string': '9007199254740993',
            '__proto__': {'constructor': {'rawJSON': '1e400', '$number': 2.0}},
            'a/\"~': [9007199254740995, -1.0000000000000001e18]}}
    }


def state_path():
    state = Path(sys.argv[2]).resolve()
    assert state.is_relative_to(Path(os.environ['TMPDIR']).resolve())
    assert state.is_dir()
    return state


def inspect(state):
    with sqlite3.connect('file:' + str(state/'planning.sqlite3') + '?mode=ro', uri=True) as conn:
        conn.row_factory = sqlite3.Row
        return {table: [dict(row) for row in conn.execute('SELECT * FROM ' + table + ' ORDER BY rowid')]
                for table in ('snapshots', 'jobs', 'accepted', 'receipts', 'audit')}


if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'serve':
        from sp5generator.models import Snapshot
        from sp5generator.webapp import create_app
        import uvicorn
        state = state_path()
        assert not (state/'planning.sqlite3').exists()
        app = create_app(str(state), start_worker=False)
        app.state.store.save_snapshot(Snapshot.model_validate(fixture()), 'local-user')
        uvicorn.run(app, host='127.0.0.1', port=0, access_log=False)
    elif mode == 'inspect':
        print(json.dumps(inspect(state_path()), ensure_ascii=False))
    elif mode == 'compare':
        rows = json.load(sys.stdin)
        for row in rows:
            left = json.loads(row['source'])
            right = json.loads(row['output'])
            for key in row.get('path', []):
                left, right = left[key], right[key]
            assert signature(left) == signature(right), (signature(left), signature(right))
        print(json.dumps({'compared': len(rows)}))
    elif mode == 'boundary':
        from sp5generator.models import Snapshot
        value = Snapshot.model_validate(fixture()).model_dump(mode='json')
        value['metadata']['padding'] = ''

        def compact():
            return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))

        budget = 16 * 1024 * 1024 + int(sys.argv[2])
        remaining = budget - len(compact().encode())
        value['metadata']['padding'] = '💡' * (remaining // 4) + 'x' * (remaining % 4)
        result = compact()
        assert len(result.encode()) == budget
        sys.stdout.write(result)
    elif mode == 'edit':
        value = json.load(sys.stdin)
        opaque = value['metadata']['opaque']
        opaque['integer'] += 2
        opaque['rows'].reverse()
        del opaque['numeric_string']
        value['employees'][0]['name'] = 'Synthetic edited'
        print(json.dumps(value, ensure_ascii=False))
    elif mode == 'strict':
        value = json.load(sys.stdin)
        key = sys.argv[2]
        if key == 'weekly':
            value['employees'][0]['contractual_weekly_minutes'] = 60.0
        else:
            value['metadata']['history_automation'] = {'minimum_days': 2.0, 'applied': []}
        print(json.dumps(value, ensure_ascii=False))
    else:
        raise ValueError(mode)
