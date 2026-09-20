"""Wie weit tragen die erteilten Freigaben? Ein Rückstand ist oft kein Planungsfehler."""

from datetime import timedelta

from sp5generator.models import Approval, Objectives
from sp5generator.solver import solve
from test_core_rules import case, shift


def roster(people=4):
    snapshot = case(n=people, shifts=[shift("mon", 5, 8, 8), shift("tue", 6, 8, 8)])
    for employee in snapshot.employees:
        employee.target_minutes = 960
    snapshot.objectives = Objectives(nights=0, weekends=0, holidays=0, wishes=0, changes=0)
    return snapshot


def reach(snapshot):
    return solve(snapshot, time_limit=10, partial=True).metrics["approval_reach"]


def test_the_report_counts_approvals_against_what_is_demanded():
    snapshot = roster()

    report = reach(snapshot)

    assert report["services"] == 1
    assert (report["people"], report["people_with_target"]) == (4, 4)
    assert report["approvals"] == 4
    assert report["approval_share_percent"] == 100.0
    assert (report["lowest_per_service"], report["median_per_service"]) == (4, 4)
    assert report["without_any_approval"] == 0


def test_people_without_any_approval_for_a_demanded_duty_are_named():
    snapshot = roster()
    snapshot.employees[0].approvals = []
    snapshot.employees[1].approvals = [Approval(
        function_id="woanders", workplace_id="w",
        valid_from=snapshot.context_start, valid_until=snapshot.context_end,
    )]

    report = reach(snapshot)

    assert report["without_any_approval"] == 2
    assert report["approvals"] == 2
    assert report["approval_share_percent"] == 50.0
    assert report["lowest_per_service"] == 2


def test_an_unreachable_target_is_reported_with_its_shortfall():
    snapshot = roster()
    # Zwei Dienste zu je acht Stunden: mehr als 960 Minuten sind nicht erreichbar.
    for employee in snapshot.employees:
        employee.target_minutes = 2000

    report = reach(snapshot)

    assert report["target_out_of_reach"] == 4
    assert report["target_out_of_reach_minutes"] == 4 * (2000 - 960)


def test_a_reachable_target_reports_no_shortfall():
    snapshot = roster()

    report = reach(snapshot)

    assert (report["target_out_of_reach"], report["target_out_of_reach_minutes"]) == (0, 0)


def test_excluded_people_are_not_part_of_the_reach():
    snapshot = roster()
    snapshot.employees[0].excluded = True

    report = reach(snapshot)

    assert (report["people"], report["people_with_target"]) == (3, 3)
    assert report["approvals"] == 3


def test_the_reach_is_reported_even_without_a_search(monkeypatch):
    """Auch der geprüfte Startplan trägt die Aussage, nicht erst die Optimierung."""
    snapshot = roster()
    snapshot.period_end = snapshot.period_start + timedelta(days=1)

    result = solve(snapshot, time_limit=10, partial=True)

    assert "approval_reach" in result.metrics
