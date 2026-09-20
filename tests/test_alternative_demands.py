"""Mehrere Schichtvarianten decken denselben Posten: eine genügt."""

from datetime import datetime, timezone

from sp5generator.models import Assignment, Demand, Interval, Objectives, Shift
from sp5generator.solver import solve
from sp5generator.validator import validate
from test_core_rules import case

UTC = timezone.utc


def night(shift_id, start_hour):
    start = datetime(2026, 1, 5, start_hour, tzinfo=UTC)
    end = datetime(2026, 1, 6, 6, tzinfo=UTC)
    return Shift(
        id=shift_id, name=f"NCT {start_hour}-06", kind="night", team_id="t",
        segments=[Interval(start=start, end=end)],
        paid_minutes=int((end - start).total_seconds() // 60),
    )


def variants(group, minimum=1, people=4):
    snapshot = case(n=people)
    snapshot.shifts = [night("long", 18), night("short", 20)]
    snapshot.demands = [
        Demand(id="d_long", shift_id="long", position_id="p",
               minimum=minimum, maximum=1, alternative_group=group),
        Demand(id="d_short", shift_id="short", position_id="p",
               minimum=minimum, maximum=1, alternative_group=group),
    ]
    snapshot.objectives = Objectives(hours=0, nights=0, weekends=0, holidays=0,
                                     wishes=0, changes=0)
    return snapshot


def test_one_staffed_variant_covers_the_post():
    snapshot = variants(group="nct")

    result = solve(snapshot, time_limit=5)

    assert result.validation.valid and result.validation.complete
    assert len(result.assignments) == 1
    assert not result.vacancies


def test_without_a_group_both_variants_are_staffed_separately():
    snapshot = variants(group=None)

    result = solve(snapshot, time_limit=5)

    assert result.validation.complete
    assert len(result.assignments) == 2


def test_a_second_person_on_the_other_variant_stays_allowed():
    snapshot = variants(group="nct")
    # „Mindestens eine, mehr erlaubt": die Höchstbesetzung je Variante gilt weiter.
    result = solve(snapshot, time_limit=5)
    andere = "d_short" if result.assignments[0].demand_id == "d_long" else "d_long"
    shift = next(s for s in snapshot.shifts
                 if s.id == next(d.shift_id for d in snapshot.demands if d.id == andere))
    erweitert = [*result.assignments, Assignment(
        employee_id="e1", demand_id=andere, segments=list(shift.segments),
    )]

    assert validate(snapshot, erweitert).valid


def test_an_empty_post_is_reported_once_not_per_variant():
    snapshot = variants(group="nct")
    for employee in snapshot.employees:
        employee.excluded = True

    result = solve(snapshot, time_limit=5, partial=True)

    assert sum(result.vacancies.values()) == 1
    assert len(result.vacancies) == 1


def test_the_independent_check_uses_the_same_rule():
    snapshot = variants(group="nct")
    einzeln = [a for a in solve(snapshot, time_limit=5).assignments]

    bericht = validate(snapshot, einzeln)

    assert bericht.valid and bericht.complete
    assert not [d for d in bericht.diagnostics if d.code == "vacancy"]
