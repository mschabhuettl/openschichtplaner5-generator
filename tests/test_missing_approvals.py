"""Der Bericht nennt die Freigaben, die eine unbesetzbare Stelle lösen würden."""

from sp5generator.models import Objectives
from sp5generator.solver import solve
from test_core_rules import case, shift


def shortage_case():
    # Zwei Dienste, zwei Funktionen: niemand ist für die zweite freigegeben.
    snapshot = case(n=2, shifts=[shift("first", 5, 8, 8), shift("second", 7, 8, 8)])
    snapshot.positions.append(snapshot.positions[0].model_copy(update={
        "id": "second_position", "name": "Funktion B", "function_id": "second_function",
    }))
    snapshot.demands[1].position_id = "second_position"
    snapshot.objectives = Objectives(hours=0, nights=0, weekends=0, holidays=0,
                                     wishes=0, changes=0)
    return snapshot


def test_blocked_demand_names_person_and_function():
    result = solve(shortage_case(), time_limit=5, partial=True)

    assert result.metrics["missing_approvals"] == [
        {"employee_id": "e0", "function_id": "second_function", "blocked_demands": 1},
        {"employee_id": "e1", "function_id": "second_function", "blocked_demands": 1},
    ]


def test_staffable_demand_needs_no_approval_hint():
    snapshot = shortage_case()
    for employee in snapshot.employees:
        employee.approvals.append(snapshot.employees[0].approvals[0].model_copy(
            update={"function_id": "second_function"}
        ))

    result = solve(snapshot, time_limit=5, partial=True)

    assert result.validation.complete
    assert result.metrics["missing_approvals"] == []


def test_other_blockers_are_not_reported_as_missing_approvals():
    snapshot = shortage_case()
    # Die zweite Funktion ist freigegeben, der Dienst bleibt trotzdem gesperrt.
    for employee in snapshot.employees:
        employee.approvals.append(snapshot.employees[0].approvals[0].model_copy(
            update={"function_id": "second_function"}
        ))
        employee.allowed_kinds = []

    result = solve(snapshot, time_limit=5, partial=True)

    assert not result.validation.complete
    assert result.metrics["missing_approvals"] == []
