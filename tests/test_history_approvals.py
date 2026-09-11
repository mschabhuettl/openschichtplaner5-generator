from datetime import timedelta
import pytest
from sp5generator.demo import make_demo
from sp5generator.history_approvals import apply_history_approvals
from sp5generator.models import Approval


def source(days=3):
    snapshot = make_demo()
    person = snapshot.employees[0]
    person.approvals = []
    snapshot.metadata['history_matrix'] = [{
        'employee_id': person.id, 'suggested_approvals': [
            {'function_id': 'synthetic-service', 'evidence_count': 20, 'evidence_days': days}
        ]}]
    return snapshot, person


def test_only_distinct_days_count_and_only_planning_period_is_granted():
    snapshot, person = source(2)
    apply_history_approvals(snapshot, 3)
    assert not person.approvals
    snapshot, person = source(3)
    apply_history_approvals(snapshot, 3)
    approval = person.approvals[0]
    assert approval.valid_from == snapshot.period_start
    assert approval.valid_until == snapshot.period_end
    assert approval.workplace_id == '*'
    assert snapshot.metadata['history_automation']['applied'][0]['evidence_days'] == 3
    apply_history_approvals(snapshot, 3)
    assert len(person.approvals) == 1


def test_existing_supervised_and_workplace_limits_are_not_widened():
    snapshot, person = source()
    old = Approval(function_id='synthetic-service', workplace_id='station-a',
                   valid_from=snapshot.period_start, valid_until=snapshot.period_end,
                   supervised=True)
    person.approvals = [old]
    before = person.model_dump()
    apply_history_approvals(snapshot)
    assert person.model_dump() == before


def test_automation_preserves_qualifications_and_personal_constraints():
    snapshot, person = source()
    person.allowed_kinds = ['day']
    before = snapshot.model_dump()
    apply_history_approvals(snapshot)
    after = snapshot.model_dump()
    for employee in before['employees']:
        employee.pop('approvals')
    for employee in after['employees']:
        employee.pop('approvals')
    assert before['employees'] == after['employees']
    for key in ('profiles', 'restrictions', 'demands', 'positions', 'unresolved', 'context_complete'):
        assert before[key] == after[key]


def test_outside_employment_gets_no_approval():
    snapshot, person = source()
    person.employment_end = snapshot.period_start - timedelta(days=1)
    apply_history_approvals(snapshot)
    assert not person.approvals


@pytest.mark.parametrize('minimum', [0, 1, -1, True, 3.5, 1098])
def test_invalid_threshold(minimum):
    snapshot, _ = source()
    with pytest.raises(ValueError):
        apply_history_approvals(snapshot, minimum)
