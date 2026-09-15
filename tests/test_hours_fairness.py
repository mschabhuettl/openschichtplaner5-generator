"""Der Fehlbetrag wird verteilt, statt einzelne Personen leer ausgehen zu lassen."""

from sp5generator.models import Objectives
from sp5generator.solver import solve
from test_core_rules import case, shift


def sharing_case(fairness):
    # Zwei Personen, gleiches Soll, drei Dienste: einer muss doppelt arbeiten.
    snapshot = case(n=2, shifts=[
        shift("mon", 5, 8, 8), shift("wed", 7, 8, 8), shift("fri", 9, 8, 8),
    ])
    for employee in snapshot.employees:
        employee.target_minutes = 1440
    snapshot.objectives = Objectives(
        hours=1, hours_fairness=fairness,
        nights=0, weekends=0, holidays=0, wishes=0, changes=0,
    )
    return snapshot


def minutes(snapshot, result):
    shifts = {s.id: s for s in snapshot.shifts}
    demands = {d.id: d for d in snapshot.demands}
    per_person = dict.fromkeys((e.id for e in snapshot.employees), 0)
    for assignment in result.assignments:
        per_person[assignment.employee_id] += shifts[
            demands[assignment.demand_id].shift_id
        ].paid_minutes
    return sorted(per_person.values())


def test_the_shortfall_is_shared_between_equal_contracts():
    snapshot = sharing_case(fairness=300)

    result = solve(snapshot, time_limit=5)

    assert result.validation.valid and result.validation.complete
    # Drei Dienste auf zwei Personen: zwei und einer, nicht drei und keiner.
    assert minutes(snapshot, result) == [480, 960]


def test_without_the_goal_the_sum_alone_decides_nothing():
    # Die Summe der Fehlstunden ist bei feststehendem Bedarf konstant; ohne das
    # Ziel darf der Plan deshalb auch eine Person leer ausgehen lassen.
    result = solve(sharing_case(fairness=0), time_limit=5)

    assert result.validation.complete
    assert result.metrics["objective_contributions"].get("hours_fairness", 0) == 0


def test_the_goal_reports_its_own_contribution():
    result = solve(sharing_case(fairness=300), time_limit=5)

    beitrag = result.metrics["objective_contributions"]["hours_fairness"]
    assert beitrag >= 0
    assert result.metrics["weighted_objective_contributions"]["hours_fairness"] == beitrag * 300


def test_people_without_any_eligible_duty_do_not_set_the_standard():
    snapshot = sharing_case(fairness=300)
    aussen = snapshot.employees[0].model_copy(deep=True, update={
        "id": "e_extern", "name": "Testperson extern", "team_ids": ["anderes"],
        "target_minutes": 1440,
    })
    snapshot.employees.append(aussen)

    result = solve(snapshot, time_limit=5)

    assert result.validation.complete
    assert minutes(snapshot, result) == [0, 480, 960]
