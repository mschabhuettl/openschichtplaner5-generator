"""Planning exclusion preserves the synthetic person's underlying records."""

import json

import pytest

from sp5generator.domain import eligibility
from sp5generator.jobs import Store
from sp5generator.models import Assignment, BoundaryWork, Snapshot
from sp5generator.solver import solve
from sp5generator.validator import validate
from test_core_rules import case, shift


def test_legacy_project_without_excluded_retains_eligibility_and_solution(tmp_path):
    snapshot = case(n=1)
    store = Store(tmp_path / "planning.sqlite3")
    original = store.save_snapshot(snapshot, "local-user")
    legacy = original.model_dump(mode="json")
    for employee in legacy["employees"]:
        employee.pop("excluded")
    with store.connect() as connection:
        connection.execute("UPDATE snapshots SET payload=? WHERE id=?",
                           (json.dumps(legacy), original.id))

    restored = store.get_snapshot(original.id, "local-user")
    assert restored == original
    assert restored.employees[0].excluded is False
    assert eligibility(restored, restored.employees[0], restored.demands[0]) == []
    result = solve(restored, time_limit=5)
    assert result.solver_status == "OPTIMAL"
    assert result.validation.valid and result.validation.complete
    assert [(a.employee_id, a.demand_id) for a in result.assignments] == [("e0", "s")]
    assert result.metrics["planning_diagnostics"]["employees"]["e0"]["exclusions"] == {}


def test_excluded_is_the_first_reason_alongside_existing_exclusions():
    snapshot = case(n=1)
    employee = snapshot.employees[0]
    employee.team_ids = []
    employee.approvals = []
    previous = eligibility(snapshot, employee, snapshot.demands[0])
    assert previous == ["team", "approval"]

    employee.excluded = True
    assert eligibility(snapshot, employee, snapshot.demands[0]) == ["excluded", *previous]


@pytest.mark.parametrize("partial", [False, True])
def test_excluded_person_gets_no_assignment_and_appears_in_candidate_statistics(partial):
    snapshot = case(n=1, shifts=[shift("a", 5, 8, 8), shift("b", 6, 8, 8)])
    employee = snapshot.employees[0]
    assert all(eligibility(snapshot, employee, demand) == [] for demand in snapshot.demands)
    employee.excluded = True

    result = solve(snapshot, time_limit=5, partial=partial)
    assert result.solver_status == ("OPTIMAL" if partial else "INFEASIBLE")
    assert result.assignments == []
    assert result.vacancies == {"a": 1, "b": 1}
    assert result.validation.valid is partial
    assert not result.validation.complete
    assert result.metrics["planning_diagnostics"]["employees"][employee.id] == {
        "positive_capacity_demands": 2,
        "eligible_demands": 0,
        "eligible_required_demands": 0,
        "exclusions": {"excluded": 2},
        "assigned_demands": 0,
        "reason": "individually_ineligible" if partial else "no_valid_plan",
    }
    shortages = [d for d in result.validation.diagnostics if d.code == "candidate_shortage"]
    assert {d.demand_id for d in shortages} == {"a", "b"}


def test_excluded_person_is_replaced_even_when_previously_assigned():
    snapshot = case()
    snapshot.assignments = [Assignment(employee_id="e0", demand_id="s")]
    snapshot.employees[0].excluded = True

    result = solve(snapshot, time_limit=5)
    assert result.validation.valid and result.validation.complete
    assert [(a.employee_id, a.demand_id) for a in result.assignments] == [("e1", "s")]
    assert result.metrics["planning_diagnostics"]["employees"]["e0"]["exclusions"] == {
        "excluded": 1,
    }
    rejected = validate(snapshot, [Assignment(employee_id="e0", demand_id="s")])
    assert not rejected.valid
    assert any(d.code == "excluded" and d.employee_id == "e0" for d in rejected.diagnostics)


@pytest.mark.parametrize("partial", [False, True])
def test_excluded_person_does_not_silently_remove_a_fixed_assignment(partial):
    snapshot = case()
    snapshot.employees[0].excluded = True
    snapshot.assignments = [Assignment(employee_id="e0", demand_id="s", fixed=True)]

    result = solve(snapshot, time_limit=5, partial=partial)
    assert result.solver_status == "INFEASIBLE"
    assert not result.validation.valid
    assert any(d.code == "fixed_conflict" and "excluded" in d.message
               for d in result.validation.diagnostics)
    assert snapshot.assignments[0].fixed


def test_exclusion_save_and_solve_preserve_person_contract_approvals_and_history(tmp_path):
    snapshot = case()
    employee = snapshot.employees[0]
    employee.target_minutes = 960
    employee.contractual_weekly_minutes = 1200
    employee.balance_minutes = 60
    employee.credit_minutes = 30
    employee.employment_fraction = 50
    employee.historical_nights = 3
    employee.historical_weekends = 4
    employee.historical_holidays = 5
    snapshot.boundary_work = [BoundaryWork(
        id="historical-duty", employee_id=employee.id, kind="night",
        segments=shift("historical-duty", 3, 20, 8, "night").segments,
    )]
    snapshot.metadata["history_matrix"] = [{
        "employee_id": employee.id, "observed_assignment_count": 7,
        "suggested_approvals": [{"function_id": "f", "evidence_days": 7}],
    }]
    snapshot.metadata["provenance"] = {
        employee.id: {"nominal_hours": {"hours_week": 20}},
    }
    store = Store(tmp_path / "planning.sqlite3")
    original = store.save_snapshot(snapshot, "local-user")
    updated = original.model_copy(deep=True)
    updated.employees[0].excluded = True
    store.save_snapshot(updated, "local-user")
    restored = store.get_snapshot(original.id, "local-user")

    assert restored.employees[0].excluded is True
    assert restored.employees[0].model_dump(exclude={"excluded"}) == (
        original.employees[0].model_dump(exclude={"excluded"})
    )
    assert restored.employees[1:] == original.employees[1:]
    assert restored.profiles == original.profiles
    assert restored.boundary_work == original.boundary_work
    assert restored.metadata == original.metadata
    assert restored.assignments == original.assignments
    assert store.list_snapshots("local-user")[0]["employee_count"] == 2
    before_solve = restored.model_dump()
    result = solve(restored, time_limit=5)
    assert result.validation.valid and result.validation.complete
    assert {a.employee_id for a in result.assignments} == {"e1"}
    assert restored.model_dump() == before_solve

    restored.employees[0].excluded = False
    assert eligibility(restored, restored.employees[0], restored.demands[0]) == []
    assert Snapshot.model_validate_json(restored.model_dump_json()) == restored
