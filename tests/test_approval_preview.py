"""Was eine fehlende Freigabe öffnen würde - ohne eine zu erteilen."""

import pytest

from sp5generator.approval_preview import approval_leverage
from sp5generator.models import Objectives
from sp5generator.solver import solve
from test_core_rules import case, shift


def two_services(n=2):
    snapshot = case(n=n, shifts=[shift("first", 5, 8, 8), shift("second", 7, 8, 8)])
    snapshot.positions.append(snapshot.positions[0].model_copy(update={
        "id": "second_position", "name": "Funktion B", "function_id": "second_function",
    }))
    snapshot.demands[1].position_id = "second_position"
    for employee in snapshot.employees:
        employee.target_minutes = 960
    snapshot.objectives = Objectives(nights=0, weekends=0, holidays=0, wishes=0, changes=0)
    return snapshot


def preview(snapshot, **kw):
    result = solve(snapshot, time_limit=10, partial=True)
    return approval_leverage(snapshot, result.assignments, **kw), result


def test_an_approval_nobody_holds_is_shown_as_closing_a_gap():
    report, result = preview(two_services())

    assert report["unstaffable_demands"] == 1
    assert {row["function_id"] for row in report["rows"]} == {"second_function"}
    for row in report["rows"]:
        assert row["unstaffable_demands"] == 1
        assert row["reachable_demands"] == 1
        assert row["reachable_minutes"] == 480
    # Die Lücke steht auch im Plan: der zweite Dienst bleibt unbesetzt.
    assert sum(result.vacancies.values()) == 1


def test_a_gap_closing_approval_outranks_one_that_only_shifts_work():
    snapshot = two_services(n=3)
    # Eine Person ist bereits für den zweiten Dienst freigegeben; damit ist er
    # besetzbar, und eine weitere Freigabe verschiebt nur noch Last.
    snapshot.employees[0].approvals.append(
        snapshot.employees[0].approvals[0].model_copy(update={"function_id": "second_function"})
    )

    report, _ = preview(snapshot)

    assert report["unstaffable_demands"] == 0
    assert all(row["unstaffable_demands"] == 0 for row in report["rows"])
    assert report["rows"] == sorted(
        report["rows"], key=lambda row: -row["usable_minutes"]
    )


def test_what_exceeds_the_own_target_is_reported_separately():
    snapshot = two_services()
    for employee in snapshot.employees:
        employee.target_minutes = 60

    report, _ = preview(snapshot)

    row = report["rows"][0]
    assert row["reachable_minutes"] == 480
    assert row["own_shortfall_minutes"] <= 60
    assert row["usable_minutes"] == row["own_shortfall_minutes"]


def test_an_approval_that_cannot_help_is_not_offered():
    snapshot = two_services()
    # Der zweite Dienst liegt außerhalb der Beschäftigung: die Freigabe allein
    # ändert daran nichts, also gehört die Zeile nicht in die Liste.
    for employee in snapshot.employees:
        employee.employment_end = snapshot.period_start

    report, _ = preview(snapshot)

    assert report["rows"] == []
    assert report["candidates"] == 0


def test_excluded_people_are_left_out():
    snapshot = two_services(n=3)
    snapshot.employees[2].excluded = True

    report, _ = preview(snapshot)

    assert "e2" not in {row["employee_id"] for row in report["rows"]}
    # Wer nicht geplant wird, hat auch keinen Rückstand, der jemanden beschäftigt.
    assert report["people_below_target"] == 2
    assert report["shortfall_minutes"] == sum(
        e.target_minutes for e in snapshot.employees[:2]
    ) - 480


def test_closing_a_gap_counts_more_than_shifting_load():
    """Eine unbesetzbare Stelle wiegt schwerer als jede Umverteilung."""
    snapshot = two_services(n=3)
    # Dritter Dienst, für den jemand freigegeben ist: dort ist nur Last zu
    # verschieben, und zwar viel mehr Zeit als beim unbesetzbaren zweiten.
    lang = snapshot.shifts[0].model_copy(deep=True, update={"id": "third"})
    lang.paid_minutes = 5000
    snapshot.shifts.append(lang)
    snapshot.positions.append(snapshot.positions[0].model_copy(update={
        "id": "third_position", "name": "Funktion C", "function_id": "third_function",
    }))
    snapshot.demands.append(snapshot.demands[0].model_copy(deep=True, update={
        "id": "third_demand", "shift_id": "third", "position_id": "third_position",
    }))
    snapshot.employees[0].approvals.append(
        snapshot.employees[0].approvals[0].model_copy(update={"function_id": "third_function"})
    )
    for employee in snapshot.employees:
        employee.target_minutes = 100000

    report, _ = preview(snapshot)

    kopf = report["rows"][0]
    assert kopf["function_id"] == "second_function", "die unbesetzbare Stelle steht vorn"
    assert kopf["unstaffable_demands"] == 1
    # Obwohl eine andere Freigabe ein Vielfaches an Zeit zugänglich machen würde.
    andere = max(row["usable_minutes"] for row in report["rows"]
                 if row["function_id"] == "third_function")
    assert andere > kopf["usable_minutes"]


def test_the_preview_changes_nothing():
    snapshot = two_services()
    result = solve(snapshot, time_limit=10, partial=True)
    before = snapshot.model_dump()

    approval_leverage(snapshot, result.assignments)

    assert snapshot.model_dump() == before


@pytest.mark.parametrize("limit", [0, -1, 1001, 1.5, True, "20"])
def test_an_impossible_limit_is_rejected(limit):
    snapshot = two_services()
    with pytest.raises(ValueError, match="1 und 1000"):
        approval_leverage(snapshot, [], limit=limit)


def test_the_summary_groups_the_same_gap_across_people():
    """Dieselbe fehlende Freigabe trifft meist viele Personen auf einmal."""
    snapshot = two_services(n=4)

    report, _ = preview(snapshot, limit=1)

    assert len(report["rows"]) == 1, "die Zeilenliste ist begrenzt"
    dienst, = report["services"]
    assert dienst["function_id"] == "second_function"
    # Die Zusammenfassung zählt alle Personen, nicht nur die gezeigten Zeilen.
    assert dienst["people"] == 4
    assert dienst["unstaffable_demands"] == 1
    assert dienst["best_usable_minutes"] == max(
        row["usable_minutes"] for row in report["rows"]
    )


def test_services_that_close_a_gap_stand_before_those_that_only_shift_work():
    snapshot = two_services(n=3)
    lang = snapshot.shifts[0].model_copy(deep=True, update={"id": "third"})
    lang.paid_minutes = 5000
    snapshot.shifts.append(lang)
    snapshot.positions.append(snapshot.positions[0].model_copy(update={
        "id": "third_position", "name": "Funktion C", "function_id": "third_function",
    }))
    snapshot.demands.append(snapshot.demands[0].model_copy(deep=True, update={
        "id": "third_demand", "shift_id": "third", "position_id": "third_position",
    }))
    snapshot.employees[0].approvals.append(
        snapshot.employees[0].approvals[0].model_copy(update={"function_id": "third_function"})
    )
    for employee in snapshot.employees:
        employee.target_minutes = 100000

    report, _ = preview(snapshot)

    assert [entry["function_id"] for entry in report["services"]] == [
        "second_function", "third_function",
    ]
