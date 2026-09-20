"""Die Zahl der Dienste wird verteilt, wo die Sollerfüllung nichts mehr aussagt."""

from sp5generator.models import Objectives
from sp5generator.solver import solve
from test_core_rules import case, shift


def roster(fairness, target=100000):
    # Vier Dienste, zwei Personen, Sollstunden weit über dem Bedarf: die
    # Sollerfüllung unterscheidet die beiden dann kaum noch.
    snapshot = case(n=2, shifts=[
        shift("mon", 5, 8, 8), shift("tue", 6, 8, 8),
        shift("wed", 7, 8, 8), shift("thu", 8, 8, 8),
    ])
    for employee in snapshot.employees:
        employee.target_minutes = target
    snapshot.objectives = Objectives(
        hours=0, hours_fairness=0, duty_fairness=fairness,
        nights=0, weekends=0, holidays=0, wishes=0, changes=0,
    )
    return snapshot


def counts(snapshot, result):
    per_person = dict.fromkeys((e.id for e in snapshot.employees), 0)
    for assignment in result.assignments:
        per_person[assignment.employee_id] += 1
    return sorted(per_person.values())


def test_duties_are_shared_instead_of_piling_up_on_one_person():
    snapshot = roster(fairness=300)

    result = solve(snapshot, time_limit=10)

    assert result.validation.valid and result.validation.complete
    assert counts(snapshot, result) == [2, 2]


def test_without_the_goal_nothing_forces_an_even_split():
    result = solve(roster(fairness=0), time_limit=10)

    assert result.validation.complete
    assert result.metrics["objective_contributions"].get("duty_fairness", 0) == 0


def test_the_goal_reports_its_own_contribution():
    result = solve(roster(fairness=300), time_limit=10)

    beitrag = result.metrics["objective_contributions"]["duty_fairness"]
    assert beitrag >= 0
    assert result.metrics["weighted_objective_contributions"]["duty_fairness"] == beitrag * 300


def test_people_without_any_eligible_duty_do_not_set_the_standard():
    snapshot = roster(fairness=300)
    aussen = snapshot.employees[0].model_copy(deep=True, update={
        "id": "e_extern", "name": "Testperson extern", "team_ids": ["anderes"],
    })
    snapshot.employees.append(aussen)

    result = solve(snapshot, time_limit=10)

    assert result.validation.complete
    # Ohne Ausnahme zöge die dauerhafte Null den gemeinsamen Maßstab nach unten.
    assert counts(snapshot, result) == [0, 2, 2]


def test_the_hours_goal_alone_cannot_do_this():
    """Bei einem Soll weit über dem Bedarf trägt die Sollerfüllung nichts bei."""
    snapshot = roster(fairness=0)
    snapshot.objectives = snapshot.objectives.model_copy(update={"hours_fairness": 300})

    result = solve(snapshot, time_limit=10)

    assert result.validation.complete
    assert result.metrics["objective_contributions"].get("hours_fairness", 0) == 0


def test_a_person_who_can_never_work_here_costs_nothing():
    snapshot = roster(fairness=300)
    snapshot.employees.append(snapshot.employees[0].model_copy(deep=True, update={
        "id": "e_extern", "name": "Testperson extern", "team_ids": ["anderes"],
    }))

    result = solve(snapshot, time_limit=10)

    # Niemand ohne Dienst verzerrt den Maßstab: null Dienste kosten null.
    assert result.metrics["objective_contributions"]["duty_fairness"] == 2 ** 2 + 2 ** 2


def test_a_shared_yardstick_would_not_steer_at_all():
    """Warum die quadrierte Anzahl und nicht der Abstand zu einem Maßstab.

    Die Summe der Dienste steht mit dem Bedarf fest. Der Abstand zu einem frei
    gewählten Maßstab rastet auf dem Median ein - bei vielen Personen ohne
    Dienst also auf null, und dann ist die Wertung genau die Gesamtzahl der
    Dienste und damit unabhängig von der Aufteilung.
    """
    snapshot = roster(fairness=300)
    # Zwei zusätzliche Personen, die alles könnten: der Median liegt bei null.
    for i in (3, 4):
        snapshot.employees.append(snapshot.employees[0].model_copy(deep=True, update={
            "id": f"e{i}", "name": f"Testperson {i + 1:03}",
        }))

    result = solve(snapshot, time_limit=10)

    verteilung = counts(snapshot, result)
    assert sum(verteilung) == 4
    # Ein Maßstabsziel ließe [4,0,0,0] genauso teuer aussehen wie [1,1,1,1].
    assert verteilung == [1, 1, 1, 1]
    assert result.metrics["objective_contributions"]["duty_fairness"] == 4
