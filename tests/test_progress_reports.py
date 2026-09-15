"""Der Solver meldet seinen Fortschritt, ohne dass die Meldung ihn gefährdet."""

from sp5generator.models import Objectives
from sp5generator.solver import solve
from test_core_rules import case, shift


def busy_case():
    snapshot = case(n=4, shifts=[
        shift("mon", 5, 8, 8), shift("tue", 6, 8, 8), shift("wed", 7, 8, 8),
    ])
    snapshot.objectives = Objectives(workday_transitions=100, isolated_days=100)
    return snapshot


def test_every_stage_and_improvement_is_reported():
    events = []

    result = solve(busy_case(), time_limit=5, partial=True, progress=events.append)

    assert result.validation.valid
    stages = [event for event in events if event.get("kind") != "incumbent"]
    improvements = [event for event in events if event.get("kind") == "incumbent"]
    assert stages, "Jede abgeschlossene Suchstufe wird gemeldet"
    assert [stage["phase"] for stage in stages] == [
        step["phase"] for step in result.parameters["search_trace"]
    ]
    assert improvements, "Zwischenlösungen werden während der Suche gemeldet"
    first = improvements[0]
    assert first["solutions"] >= 1
    assert 0 <= first["search_seconds"] <= first["elapsed_seconds"] <= 5
    assert first["objective"] >= first["bound"]


def test_a_failing_report_never_stops_the_calculation():
    def broken(_event):
        raise RuntimeError("Anzeige kaputt")

    result = solve(busy_case(), time_limit=5, partial=True, progress=broken)

    assert result.validation.valid and result.validation.complete
    assert result.parameters["search_trace"]


def test_without_a_reporter_the_trace_is_unchanged():
    quiet = solve(busy_case(), time_limit=5, partial=True)
    events = []
    loud = solve(busy_case(), time_limit=5, partial=True, progress=events.append)

    assert [step["phase"] for step in quiet.parameters["search_trace"]] == [
        step["phase"] for step in loud.parameters["search_trace"]
    ]
    assert len(quiet.assignments) == len(loud.assignments)
