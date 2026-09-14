from datetime import date, timedelta

import pytest

from sp5generator.models import Assignment, BoundaryWork, Objectives, Restriction, Snapshot
from sp5generator.solver import solve
from sp5generator.validator import validate
from test_core_rules import case, shift


def shape_objectives(weight=0):
    # Das kleine Änderungsgewicht hält die Ausgangszuteilung eindeutig.
    return Objectives(
        hours=0, nights=0, weekends=0, holidays=0, wishes=0, changes=1,
        block_shape=weight,
    )


def fragmented_case():
    snapshot = case(shifts=[shift(f"d{day}", day, 8, 8) for day in range(5, 11)])
    snapshot.assignments = [
        Assignment(employee_id="e0" if day in (5, 8, 9) else "e1", demand_id=f"d{day}")
        for day in range(5, 11)
    ]
    snapshot.objectives = shape_objectives()
    return snapshot


def assigned_pairs(snapshot):
    result = solve(snapshot, time_limit=5)
    assert result.solver_status == "OPTIMAL"
    assert validate(snapshot, result.assignments).complete
    return {(a.employee_id, a.demand_id) for a in result.assignments}


@pytest.mark.parametrize("explicit_weight", [False, True])
def test_block_shape_zero_preserves_fragmented_assignments(explicit_weight):
    original = fragmented_case().model_dump(mode="json")
    if explicit_weight:
        original["objectives"]["block_shape"] = 0
    else:
        original["objectives"].pop("block_shape", None)
    snapshot = Snapshot.model_validate(original)
    assert snapshot.objectives.block_shape == 0

    assert assigned_pairs(snapshot) == {
        (a.employee_id, a.demand_id) for a in snapshot.assignments
    }


def test_block_shape_prefers_three_day_blocks_to_single_plus_pair():
    snapshot = fragmented_case()
    snapshot.objectives.block_shape = 1000

    pairs = assigned_pairs(snapshot)

    assert len(pairs) == 6
    assert {demand_id for _, demand_id in pairs} == {f"d{day}" for day in range(5, 11)}
    # Beide Personen behalten drei Diensttage; aus je 1 + 2 wird je ein Dreierblock.
    assert {
        frozenset(demand_id for employee_id, demand_id in pairs if employee_id == employee.id)
        for employee in snapshot.employees
    } == {frozenset({"d5", "d6", "d7"}), frozenset({"d8", "d9", "d10"})}


@pytest.mark.parametrize("employees", [1, 2])
def test_block_shape_splits_seven_days_when_shorter_blocks_can_cover_demand(employees):
    snapshot = case(n=employees, shifts=[shift(f"d{day}", day, 8, 8) for day in range(5, 12)])
    snapshot.assignments = [
        Assignment(employee_id="e0", demand_id=f"d{day}") for day in range(5, 12)
    ]
    if employees == 2:
        # Die zweite Person kann die letzten drei Tage als eigenen Block übernehmen.
        snapshot.restrictions = [
            Restriction(employee_id="e1", shift_id=f"d{day}", level=2)
            for day in range(5, 9)
        ]
    snapshot.objectives = shape_objectives(1000)

    pairs = assigned_pairs(snapshot)

    assert len(pairs) == 7
    assert pairs == {
        ("e1" if employees == 2 and day >= 9 else "e0", f"d{day}")
        for day in range(5, 12)
    }
    # Ohne Alternative bleibt auch ein Siebenerblock zulässig: Das Ziel ist weich.


@pytest.mark.parametrize("following_boundary_day", [False, True])
def test_block_shape_closes_open_block_at_period_end(following_boundary_day):
    snapshot = case(n=1, shifts=[shift(f"d{day}", day, 8, 8) for day in range(8, 12)])
    snapshot.demands[-1].minimum = 0
    snapshot.assignments = [
        Assignment(employee_id="e0", demand_id=f"d{day}") for day in range(8, 12)
    ]
    if following_boundary_day:
        # Auch wenn der zusätzliche Folgetag arbeitet, muss der Automat abschließen.
        snapshot.boundary_work = [BoundaryWork(
            id="after", employee_id="e0", segments=shift("after", 12, 8, 8).segments,
            kind="day",
        )]
    snapshot.objectives = shape_objectives()
    assert assigned_pairs(snapshot) == {("e0", f"d{day}") for day in range(8, 12)}

    snapshot.objectives.block_shape = 1000

    # Der optionale vierte Tag würde nur durch eine übersehene Abschlussstrafe bleiben.
    assert assigned_pairs(snapshot) == {("e0", f"d{day}") for day in range(8, 11)}


@pytest.mark.parametrize("boundary_days", [
    (5, 6, 7),
    (2, 3, 4, 5, 6, 7),
    (1, 2, 3, 4, 5, 6, 7),
    (3, 5, 6, 7),
])
def test_block_shape_continues_consecutive_boundary_starts(boundary_days):
    snapshot = case(shifts=[shift("first", 8, 8, 8)])
    snapshot.period_start = date(2026, 1, 8)
    snapshot.assignments = [Assignment(employee_id="e1", demand_id="first")]
    snapshot.boundary_work = [
        BoundaryWork(
            id=f"before-{day}", employee_id="e0",
            segments=shift(f"before-{day}", day, 8, 8).segments,
            kind="day",
        )
        for day in boundary_days
    ]
    snapshot.objectives = shape_objectives()
    assert assigned_pairs(snapshot) == {("e1", "first")}

    snapshot.objectives.block_shape = 1000

    # Nach drei Randtagen ist dies der vierte Blocktag, günstiger als ein neuer
    # Einzeltag. Eine Lücke beendet den Rückblick; ab sechs bleibt er gedeckelt.
    assert assigned_pairs(snapshot) == {("e0", "first")}


def test_block_shape_counts_duty_starts_without_overnight_spill():
    snapshot = case(shifts=[
        shift("first", 5, 8, 8), shift("second", 6, 8, 8),
        shift("third_night", 7, 22, 8, "night"),
    ])
    snapshot.assignments = [
        Assignment(employee_id="e0", demand_id="first"),
        Assignment(employee_id="e0", demand_id="second"),
        Assignment(employee_id="e1", demand_id="third_night"),
    ]
    snapshot.objectives = shape_objectives(1000)

    # Drei Dienstbeginne ergeben Länge drei, obwohl vier Kalendertage berührt sind.
    assert assigned_pairs(snapshot) == {
        ("e0", "first"), ("e0", "second"), ("e0", "third_night"),
    }


def test_block_shape_boundary_overnight_spill_does_not_bridge_missing_start():
    snapshot = case(shifts=[shift("first", 8, 18, 4)])
    snapshot.period_start = date(2026, 1, 8)
    snapshot.assignments = [Assignment(employee_id="e1", demand_id="first")]
    snapshot.boundary_work = [
        BoundaryWork(
            id=f"before-{day}", employee_id="e0",
            segments=shift(f"before-{day}", day, 22, 8, "night").segments,
            kind="night",
        )
        for day in (5, 6)
    ]
    snapshot.objectives = shape_objectives(1000)

    assert snapshot.boundary_work[-1].segments[-1].end.date() == (
        snapshot.period_start - timedelta(days=1)
    )
    # Der Überhang am Vortag beginnt dort keinen Dienst; beide Personen hätten
    # einen Einzeltag. Daher bleibt die ursprüngliche Zuteilung bestehen.
    assert assigned_pairs(snapshot) == {("e1", "first")}
