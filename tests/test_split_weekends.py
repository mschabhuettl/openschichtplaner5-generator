from datetime import date

import pytest

from sp5generator.models import Assignment, Objectives, Restriction, Snapshot
from sp5generator.solver import solve
from sp5generator.validator import validate
from test_core_rules import case, shift


def weekend_case():
    snapshot = case(shifts=[shift("sat", 10, 8, 8), shift("sun", 11, 8, 8)])
    snapshot.assignments = [
        Assignment(employee_id="e0", demand_id="sat"),
        Assignment(employee_id="e1", demand_id="sun"),
    ]
    # Das kleine Änderungsgewicht macht die bisherige Aufteilung eindeutig.
    snapshot.objectives = Objectives(
        hours=0, nights=0, weekends=0, holidays=0, wishes=0, changes=1,
    )
    return snapshot


@pytest.mark.parametrize("explicit_weight", [False, True])
def test_split_weekends_zero_preserves_split_assignments(explicit_weight):
    original = weekend_case().model_dump(mode="json")
    if explicit_weight:
        original["objectives"]["split_weekends"] = 0
    else:
        original["objectives"].pop("split_weekends", None)
    snapshot = Snapshot.model_validate(original)
    assert snapshot.objectives.split_weekends == 0

    result = solve(snapshot, time_limit=5)

    assert result.solver_status == "OPTIMAL"
    assert validate(snapshot, result.assignments).complete
    assert {(a.employee_id, a.demand_id) for a in result.assignments} == {
        ("e0", "sat"), ("e1", "sun"),
    }


def test_split_weekends_high_weight_assigns_both_days_to_one_person():
    snapshot = weekend_case()
    snapshot.objectives.split_weekends = 1000

    result = solve(snapshot, time_limit=5)

    assert result.solver_status == "OPTIMAL"
    assert validate(snapshot, result.assignments).complete
    assert len(result.assignments) == 2
    assert {a.demand_id for a in result.assignments} == {"sat", "sun"}
    assert len({a.employee_id for a in result.assignments}) == 1


def test_split_weekends_friday_night_does_not_require_sunday_assignment():
    snapshot = case(shifts=[
        shift("fri_night", 9, 22, 8, "night"), shift("sun", 11, 8, 8),
    ])
    snapshot.assignments = [
        Assignment(employee_id="e0", demand_id="fri_night"),
        Assignment(employee_id="e1", demand_id="sun"),
    ]
    snapshot.restrictions = [
        Restriction(employee_id="e1", shift_id="fri_night", level=2),
    ]
    snapshot.objectives = Objectives(
        hours=0, nights=0, weekends=0, holidays=0, wishes=0, changes=1,
        split_weekends=1000,
    )

    result = solve(snapshot, time_limit=5)

    assert result.solver_status == "OPTIMAL"
    assert validate(snapshot, result.assignments).complete
    # Freitag 22 bis Samstag 06 erzeugt keinen Samstagsdienst für e0.
    assert {(a.employee_id, a.demand_id) for a in result.assignments} == {
        ("e0", "fri_night"), ("e1", "sun"),
    }


def test_split_weekends_saturday_night_requires_real_sunday_assignment():
    snapshot = case(shifts=[
        shift("sat_night", 10, 22, 8, "night"), shift("sun", 11, 18, 4),
    ])
    snapshot.assignments = [
        Assignment(employee_id="e0", demand_id="sat_night"),
        Assignment(employee_id="e1", demand_id="sun"),
    ]
    # e1 hat keine Samstagsmöglichkeit und damit selbst keine Wochenendkopplung.
    snapshot.restrictions = [
        Restriction(employee_id="e1", shift_id="sat_night", level=2),
    ]
    snapshot.objectives = Objectives(
        hours=0, nights=0, weekends=0, holidays=0, wishes=0, changes=1,
        split_weekends=1000,
    )

    result = solve(snapshot, time_limit=5)

    assert result.solver_status == "OPTIMAL"
    assert validate(snapshot, result.assignments).complete
    # Das Dienstende am Sonntag ersetzt keinen Sonntagsbeginn; 12 h Ruhe bleiben.
    assert {(a.employee_id, a.demand_id) for a in result.assignments} == {
        ("e0", "sat_night"), ("e0", "sun"),
    }


@pytest.mark.parametrize("day", [10, 11])
def test_split_weekends_skips_weekends_with_only_one_day_of_demand(day):
    snapshot = case(n=1, shifts=[shift("single", day, 8, 8)])
    snapshot.assignments = [Assignment(employee_id="e0", demand_id="single")]
    # Optionaler Bedarf macht eine fälschliche Strafe an der Zuteilung sichtbar.
    snapshot.demands[0].minimum = 0
    snapshot.objectives = Objectives(
        hours=0, nights=0, weekends=0, holidays=0, wishes=0, changes=1,
        split_weekends=1000,
    )

    result = solve(snapshot, time_limit=5)

    assert result.solver_status == "OPTIMAL"
    assert validate(snapshot, result.assignments).complete
    assert {(a.employee_id, a.demand_id) for a in result.assignments} == {
        ("e0", "single"),
    }


def test_split_weekends_requires_work_opportunities_for_the_same_person():
    snapshot = weekend_case()
    snapshot.objectives.split_weekends = 1000
    snapshot.restrictions = [
        Restriction(employee_id="e0", shift_id="sun", level=2),
        Restriction(employee_id="e1", shift_id="sat", level=2),
    ]
    # Ohne Mindestbedarf könnte eine fälschliche Strafe beide Dienste entfernen.
    for demand in snapshot.demands:
        demand.minimum = 0

    result = solve(snapshot, time_limit=5)

    assert result.solver_status == "OPTIMAL"
    assert validate(snapshot, result.assignments).complete
    assert {(a.employee_id, a.demand_id) for a in result.assignments} == {
        ("e0", "sat"), ("e1", "sun"),
    }


@pytest.mark.parametrize("outside_day", ["sat", "sun"])
def test_split_weekends_skips_period_edges_even_with_fixed_context(outside_day):
    snapshot = weekend_case()
    snapshot.objectives.split_weekends = 1000
    if outside_day == "sat":
        snapshot.period_start = date(2026, 1, 11)
        inside_day = "sun"
    else:
        snapshot.period_end = date(2026, 1, 10)
        inside_day = "sat"
    # Fixierter Kontext hält beide Tagesvariablen für dieselbe Person vorhanden.
    snapshot.assignments = [
        Assignment(employee_id="e0", demand_id=outside_day, fixed=True),
        Assignment(employee_id="e1", demand_id=inside_day),
    ]

    result = solve(snapshot, time_limit=5)

    assert result.solver_status == "OPTIMAL"
    assert validate(snapshot, result.assignments).complete
    assert {(a.employee_id, a.demand_id, a.fixed) for a in result.assignments} == {
        ("e0", outside_day, True), ("e1", inside_day, False),
    }
