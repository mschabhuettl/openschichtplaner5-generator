"""Native handoffs cannot trust constructor time, identity or model_copy."""
from datetime import date

import pytest
from pydantic import ValidationError

from sp5generator.domain import input_diagnostics
from sp5generator.history_approvals import apply_history_approvals
from sp5generator.jobs import Store
from sp5generator.models import Snapshot
from sp5generator.validator import PreparedValidator
from sp5generator.webapp import check_project_structure
from test_review_budget_roundtrip import db_state, fixture, padded, units


@pytest.mark.parametrize('consumer', ['save', 'write', 'structure', 'diagnostics', 'prepared', 'revalidate', 'solver'])
@pytest.mark.parametrize('change', ['mutate', 'model-copy'])
def test_native_budget_guard_precedes_dump_and_deepcopy(tmp_path, monkeypatch, consumer, change):
    store = Store(tmp_path / 'state.sqlite')
    original = store.save_snapshot(Snapshot.model_validate(fixture()), 'local-user')
    before = db_state(store)
    data = {f'v{i}': '1' for i in range(50001 - units(original))}
    if change == 'model-copy':
        candidate = original.model_copy(update={'software_versions': data}, deep=True)
    else:
        candidate = original
        candidate.software_versions = data
    assert units(candidate) == 50001

    def forbidden(*args, **kwargs):
        raise AssertionError('An over-budget native value reached dump/deepcopy')

    monkeypatch.setattr(Snapshot, 'model_dump', forbidden)
    monkeypatch.setattr(Snapshot, 'model_dump_json', forbidden)
    monkeypatch.setattr(Snapshot, 'model_copy', forbidden)
    if consumer == 'diagnostics':
        issues = input_diagnostics(candidate)
        assert [issue.code for issue in issues] == ['size_limit']
    elif consumer == 'solver':
        from sp5generator.solver import solve
        result = solve(candidate, 1)
        assert result.solver_status == 'MODEL_INVALID'
        assert not result.validation.valid and not result.assignments
        assert [issue.code for issue in result.validation.diagnostics] == ['size_limit']
        assert result.snapshot_id == candidate.id
        assert result.snapshot_hash == ''  # No hashing/dumping rejected input.
    else:
        with pytest.raises(ValueError, match=r'\[size_limit\]'):
            if consumer == 'save':
                store.save_snapshot(candidate, 'local-user')
            elif consumer == 'write':
                with store.transaction() as conn:
                    store._write_snapshot(conn, candidate, 'local-user')
            elif consumer == 'structure':
                check_project_structure(candidate)
            elif consumer == 'prepared':
                PreparedValidator(candidate)
            else:
                Snapshot.model_validate(candidate)
    assert db_state(store) == before


@pytest.mark.parametrize('target', [49988, 49989])
def test_history_handoff_charges_new_approvals_and_preserves_under_limit(target):
    snapshot = Snapshot.model_validate(padded(target))
    snapshot.metadata['history_matrix'] = [{'employee_id': 'p', 'suggested_approvals': [
        {'function_id': 'new-role', 'evidence_days': 3},
        {'function_id': 'other-role', 'evidence_days': 3}]}]
    if target == 49989:
        with pytest.raises(ValueError, match=r'\[size_limit\]'):
            apply_history_approvals(snapshot)
    else:
        result = apply_history_approvals(snapshot)
        assert units(result) == 50000
        assert [a.function_id for a in result.employees[0].approvals] == ['role', 'new-role', 'other-role']
        assert Snapshot.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize('adapter', ['local', 'api'])
@pytest.mark.parametrize('excess', [False, True])
def test_native_importer_final_growth_before_handoff(monkeypatch, adapter, excess):
    """Only source transport/import_snapshot doubled; final producer code is real."""
    import sp5generator.sp5_adapter as local
    import sp5generator.api_adapter as remote
    added = 1 if adapter == 'local' else 3
    snapshot = Snapshot.model_validate(padded(50000 - added + int(excess)))
    if adapter == 'local':
        monkeypatch.setattr(local, '_source_database', lambda *a: (object(), {}))
        monkeypatch.setattr(local, '_source_fingerprint', lambda *a: 'synthetic')
        monkeypatch.setattr(local, 'import_snapshot', lambda *a, **kw: snapshot)
        monkeypatch.setattr(local, 'historical_matrix', lambda *a: [])
        def run():
            return local.import_directory('/not-read', date(2026, 1, 5), date(2026, 1, 5))
    else:
        class Client:
            def authorize(self):
                pass

            def verify(self):
                return 'synthetic'

        class Database:
            def __init__(self, *args):
                pass

            def get_groups(self):
                return []

            def get_group_members(self, *args):
                return []

            def get_employees(self):
                return []

        monkeypatch.setattr(remote, 'APIClient', Client)
        monkeypatch.setattr(remote, '_Database', Database)
        monkeypatch.setattr(remote, 'resolve_group_selection', lambda *a: [1])
        monkeypatch.setattr(remote, 'import_snapshot', lambda *a, **kw: snapshot)
        monkeypatch.setattr(remote, 'historical_matrix', lambda *a: [])
        def run():
            return remote.import_api(date(2026, 1, 5), date(2026, 1, 5), '1', 'UTC')
    if excess:
        with pytest.raises(ValueError, match=r'\[size_limit\]'):
            run()
    else:
        output = run()
        assert units(output) == 50000
        assert Snapshot.model_validate_json(output.model_dump_json()) == output


def test_generated_project_real_boundary():
    from sp5generator.project_creation import ProjectCreateRequest, create_project
    request = {'project_name': 'Synthetic', 'period_start': '2026-01-05', 'period_end': '2026-01-07',
               'timezone': 'UTC', 'people': [{'name': f'P{i}', 'target_hours': 1} for i in range(817)],
               'positions': [{'name': f'S{i}'} for i in range(5)],
               'shift_templates': [{'name': 'Synthetic duty', 'kind': 'day',
                                    'start_time': '08:00', 'end_time': '09:00',
                                    'weekdays': list(range(7)),
                                    'demands': [{'position': 0, 'minimum': 1, 'maximum': 1}]}],
               'rules': {'min_rest_hours': 0, 'max_consecutive_work_days': 6,
                         'max_consecutive_nights': 3, 'max_daily_hours': 12,
                         'max_weekly_hours': 48, 'weekly_rest_hours': 0},
               'rules_confirmed': True, 'approvals_confirmed': True, 'context_duty_free_confirmed': True}
    # Actual request shape is checked, not a fake generator output.
    request = ProjectCreateRequest.model_validate(request)
    with pytest.raises(ValidationError, match=r'\[size_limit\]'):
        create_project(request)
    request.people.pop()
    good = create_project(request)
    assert units(good) <= 50000
    assert Snapshot.model_validate_json(good.model_dump_json()) == good


@pytest.mark.parametrize('capacity', [49900, 50000])
def test_internal_repair_budget_keeps_real_valid_incumbent(monkeypatch, capacity):
    from test_repair_phase import controlled_run, repair_case, repair_trace
    from sp5generator.validator import validate
    snapshot = repair_case()
    snapshot.software_versions.update({f'v{i}': '1' for i in range(capacity - units(snapshot))})
    assert units(snapshot) == capacity
    original = snapshot.model_dump_json()
    baseline, _, _ = controlled_run(monkeypatch, snapshot, repair=False)
    result, rounds, _ = controlled_run(monkeypatch, snapshot)
    assert result.validation.valid and result.assignments
    assert validate(snapshot, result.assignments).valid
    assert result.assignments == baseline.assignments
    assert result.metrics == baseline.metrics
    assert snapshot.model_dump_json() == original
    if capacity == 50000:
        assert not rounds, 'Oversized candidate must stop before recursive solving/copying'
        assert len(repair_trace(result)) == 1
        assert repair_trace(result)[0]['reason'] == 'size_limit'
        assert repair_trace(result)[0]['accepted'] is False
    else:
        assert rounds
        assert all(units(r['snapshot']) <= 50000 for r in rounds)
