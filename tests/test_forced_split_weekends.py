"""Der Bedarf erzwingt Teilungen, die keine Freigabe auflöst."""

from sp5generator.models import Objectives
from sp5generator.solver import solve
from test_core_rules import case, shift


def demand_case(sat_minimum, sat_maximum, sun_minimum, sun_maximum, people=4):
    snapshot = case(n=people, shifts=[shift("sat", 10, 8, 8), shift("sun", 11, 8, 8)])
    snapshot.demands[0].minimum, snapshot.demands[0].maximum = sat_minimum, sat_maximum
    snapshot.demands[1].minimum, snapshot.demands[1].maximum = sun_minimum, sun_maximum
    snapshot.objectives = Objectives(
        split_weekends=1, hours=0, nights=0, weekends=0, holidays=0,
        wishes=0, changes=0,
    )
    return snapshot


def forced(result):
    return [
        diagnostic for diagnostic in result.validation.diagnostics
        if diagnostic.code == "split_weekend_demand"
    ]


def test_unequal_weekend_demand_reports_the_forced_number():
    result = solve(demand_case(3, 3, 1, 1), time_limit=5)

    hint, = forced(result)
    assert hint.date == "2026-01-10"
    assert "3" in hint.message and "1" in hint.message
    assert "2 Personen müssen" in hint.message
    assert result.metrics["split_weekends_forced_by_demand"] == 2


def test_single_forced_split_is_named_in_the_singular():
    result = solve(demand_case(2, 2, 1, 1), time_limit=5)

    hint, = forced(result)
    assert "Eine Person muss" in hint.message
    assert result.metrics["split_weekends_forced_by_demand"] == 1


def test_equal_weekend_demand_forces_nothing():
    result = solve(demand_case(2, 2, 2, 2), time_limit=5)

    assert not forced(result)
    assert result.metrics["split_weekends_forced_by_demand"] == 0


def test_open_upper_limit_on_the_weaker_day_absorbs_the_difference():
    result = solve(demand_case(3, 3, 1, None), time_limit=5)

    assert not forced(result)
    assert result.metrics["split_weekends_forced_by_demand"] == 0


def test_disabled_objective_reports_no_forced_splits():
    snapshot = demand_case(3, 3, 1, 1)
    snapshot.objectives.split_weekends = 0

    result = solve(snapshot, time_limit=5)

    assert not forced(result)
    assert result.metrics["split_weekends_forced_by_demand"] == 0


def test_plan_reports_every_counted_split_not_only_the_weighted_ones():
    # Am Sonntag gibt es überhaupt keinen Dienst: die gewichtete Wertung sieht
    # diese Teilung nicht, der Bericht muss sie trotzdem nennen.
    snapshot = case(n=1, shifts=[shift("sat", 10, 8, 8)])
    snapshot.objectives = Objectives(
        split_weekends=1, hours=0, nights=0, weekends=0, holidays=0,
        wishes=0, changes=0,
    )

    result = solve(snapshot, time_limit=5)

    assert result.validation.complete
    assert result.metrics["objective_contributions"].get("split_weekends", 0) == 0
    assert result.metrics["split_weekends_in_plan"] == 1


def test_a_friday_night_reaching_into_saturday_counts_towards_the_floor():
    # Ein Freitagnachtdienst belegt den Samstag mit; damit steht der Samstag
    # rechnerisch bei zwei Besetzungen gegen eine am Sonntag.
    snapshot = case(n=4, shifts=[
        shift("fri_night", 9, 22, 8, "night"), shift("sat", 10, 8, 8),
        shift("sun", 11, 8, 8),
    ])
    snapshot.objectives = Objectives(
        split_weekends=1, hours=0, nights=0, weekends=0, holidays=0,
        wishes=0, changes=0,
    )

    result = solve(snapshot, time_limit=5)

    hint, = forced(result)
    assert "am Samstag 2 und am Sonntag 1" in hint.message
    assert result.metrics["split_weekends_forced_by_demand"] == 1
