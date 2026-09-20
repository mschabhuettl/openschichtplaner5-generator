"""Eine persönliche Obergrenze begrenzt die Zuteilung im Planungszeitraum hart."""

import pytest

from sp5generator.models import Objectives
from sp5generator.solver import solve
from test_core_rules import case, shift


def roster(cap=None, people=2):
    snapshot = case(n=people, shifts=[
        shift("mon", 5, 8, 8), shift("tue", 6, 8, 8),
        shift("wed", 7, 8, 8), shift("thu", 8, 8, 8),
    ])
    for employee in snapshot.employees:
        employee.target_minutes = 100000
    snapshot.employees[0].max_period_minutes = cap
    snapshot.objectives = Objectives(
        hours=1, nights=0, weekends=0, holidays=0, wishes=0, changes=0,
    )
    return snapshot


def worked(snapshot, result, employee_id):
    shifts = {s.id: s for s in snapshot.shifts}
    demands = {d.id: d for d in snapshot.demands}
    return sum(shifts[demands[a.demand_id].shift_id].paid_minutes
               for a in result.assignments if a.employee_id == employee_id)


@pytest.mark.parametrize("cap,most", [(0, 0), (480, 480), (960, 960)])
def test_the_cap_limits_what_one_person_is_given(cap, most):
    snapshot = roster(cap=cap)

    result = solve(snapshot, time_limit=10, partial=True)

    assert worked(snapshot, result, "e0") <= most
    # Die übrigen Dienste bleiben besetzt, sie wandern nur zu jemand anderem.
    assert len(result.assignments) == 4


def test_without_a_cap_nothing_limits_the_single_person():
    """Ohne Grenze darf eine Person alles übernehmen - das ist der Ausgangszustand."""
    snapshot = roster(cap=None, people=1)

    result = solve(snapshot, time_limit=10, partial=True)

    assert worked(snapshot, result, "e0") == 4 * 480


def test_a_cap_below_the_demand_leaves_the_rest_open_instead_of_breaking():
    snapshot = roster(cap=480, people=1)

    result = solve(snapshot, time_limit=10, partial=True)

    assert worked(snapshot, result, "e0") == 480
    assert sum(result.vacancies.values()) == 3


def test_the_cap_is_a_hard_rule_not_a_preference():
    snapshot = roster(cap=480, people=1)
    # Selbst wenn die Stundenwertung massiv zum Auffüllen drängt.
    snapshot.objectives = snapshot.objectives.model_copy(update={"hours": 10000})

    result = solve(snapshot, time_limit=10, partial=True)

    assert worked(snapshot, result, "e0") == 480
