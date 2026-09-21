from datetime import date

import pytest

from sp5generator.demo import make_demo
from sp5generator.models import Assignment
from sp5generator.replacement import replacement_candidates
from sp5generator.solver import solve


@pytest.fixture(scope="module")
def planned():
    snapshot = make_demo()
    result = solve(snapshot, time_limit=20, partial=True)
    assert result.assignments
    return snapshot, result.assignments


def _absent(planned, day):
    snapshot, assignments = planned
    from sp5generator.timeutils import bounds, local_day
    shifts = {s.id: s for s in snapshot.shifts}
    demands = {d.id: d for d in snapshot.demands}
    for a in assignments:
        shift = shifts[demands[a.demand_id].shift_id]
        if local_day(bounds(shift)[0], snapshot.timezone) == day:
            return a.employee_id
    raise AssertionError("no duty on that day")


def test_only_free_and_approved_people_are_offered(planned):
    snapshot, assignments = planned
    day = date(2026, 1, 8)
    sick = _absent(planned, day)
    report = replacement_candidates(snapshot, assignments, sick, day, day)
    assert report["duties"], "the absence frees at least one duty"
    busy = {a.employee_id for a in assignments}
    for duty in report["duties"]:
        offered = {c["employee_id"] for c in duty["candidates"]}
        assert sick not in offered
        # Nobody already on this very duty is offered as a stand-in for it.
        assert offered.isdisjoint({a.employee_id for a in assignments
                                   if a.demand_id == duty["demand_id"]})
        assert offered <= {e.id for e in snapshot.employees}
        assert busy  # the draft really is populated
        assert duty["date"] == str(day)


def test_the_longest_wait_comes_first(planned):
    snapshot, assignments = planned
    day = date(2026, 1, 8)
    sick = _absent(planned, day)
    report = replacement_candidates(snapshot, assignments, sick, day, day)
    for duty in report["duties"]:
        waits = [c["days_since_last_duty"] for c in duty["candidates"]]
        ranked = [10**6 if w is None else w for w in waits]
        assert ranked == sorted(ranked, reverse=True)


def test_a_multi_day_absence_names_who_can_cover_all_of_it(planned):
    snapshot, assignments = planned
    sick = _absent(planned, date(2026, 1, 8))
    report = replacement_candidates(snapshot, assignments, sick,
                                    date(2026, 1, 8), date(2026, 1, 12))
    per_duty = [{c["employee_id"] for c in duty["candidates"]} for duty in report["duties"]]
    expected = set.intersection(*per_duty) if per_duty else set()
    assert set(report["covers_whole_absence"]) == expected
    assert report["absent_from"] == "2026-01-08" and report["absent_until"] == "2026-01-12"


def test_an_absence_without_any_affected_duty_frees_nothing(planned):
    snapshot, assignments = planned
    report = replacement_candidates(snapshot, assignments, snapshot.employees[0].id,
                                    date(2025, 12, 1), date(2025, 12, 5))
    assert report["duties"] == [] and report["covers_whole_absence"] == []


def test_a_blocked_person_is_counted_with_a_reason_not_silently_dropped(planned):
    snapshot, assignments = planned
    day = date(2026, 1, 8)
    sick = _absent(planned, day)
    excluded = snapshot.model_copy(deep=True)
    for person in excluded.employees:
        if person.id != sick:
            person.excluded = True
    report = replacement_candidates(excluded, assignments, sick, day, day)
    for duty in report["duties"]:
        assert duty["candidates"] == []
        assert duty["blocked"].get("excluded")


@pytest.mark.parametrize("start,end", [
    (date(2026, 1, 9), date(2026, 1, 8)),
    ("2026-01-08", date(2026, 1, 8)),
    (date(2026, 1, 8), None),
])
def test_an_impossible_absence_window_is_rejected(planned, start, end):
    snapshot, assignments = planned
    with pytest.raises(ValueError):
        replacement_candidates(snapshot, assignments, snapshot.employees[0].id, start, end)


def test_an_unknown_person_is_rejected(planned):
    snapshot, assignments = planned
    with pytest.raises(ValueError, match="gehört nicht"):
        replacement_candidates(snapshot, assignments, "wer-auch-immer",
                               date(2026, 1, 8), date(2026, 1, 8))


def test_the_search_never_changes_the_plan(planned):
    snapshot, assignments = planned
    before = snapshot.model_dump()
    kept = [Assignment(**a.model_dump()) for a in assignments]
    replacement_candidates(snapshot, assignments, _absent(planned, date(2026, 1, 8)),
                           date(2026, 1, 5), date(2026, 1, 18))
    assert snapshot.model_dump() == before
    assert [a.model_dump() for a in assignments] == [a.model_dump() for a in kept]


def test_someone_already_working_at_that_hour_is_not_offered(planned):
    """Free means free: an own duty at the same hour blocks the stand-in."""
    from sp5generator.models import BoundaryWork
    snapshot, assignments = planned
    day = date(2026, 1, 8)
    sick = _absent(planned, day)
    open_report = replacement_candidates(snapshot, assignments, sick, day, day)
    duty = open_report["duties"][0]
    free = duty["candidates"][0]["employee_id"]

    shift = {s.id: s for s in snapshot.shifts}[duty["shift_id"]]
    busy = snapshot.model_copy(deep=True)
    busy.boundary_work.append(BoundaryWork(
        id="eigener-dienst", employee_id=free, segments=shift.segments, kind=shift.kind,
    ))
    report = replacement_candidates(busy, assignments, sick, day, day)
    same = next(d for d in report["duties"] if d["demand_id"] == duty["demand_id"])
    assert free not in {c["employee_id"] for c in same["candidates"]}
    assert same["blocked"].get("overlap"), same["blocked"]
    # Everyone else keeps their place; only the now-busy person drops out.
    assert {c["employee_id"] for c in same["candidates"]} == \
        {c["employee_id"] for c in duty["candidates"]} - {free}


def test_the_absent_person_appears_nowhere_not_even_as_a_blocked_count(planned):
    snapshot, assignments = planned
    day = date(2026, 1, 8)
    sick = _absent(planned, day)
    report = replacement_candidates(snapshot, assignments, sick, day, day)
    others = len(snapshot.employees) - 1
    for duty in report["duties"]:
        assert sick not in {c["employee_id"] for c in duty["candidates"]}
        assert sum(duty["blocked"].values()) + len(duty["candidates"]) == others


def test_someone_blocked_twice_over_is_counted_once(planned):
    """Die Gründe sind eine Personenzahl, keine Aufzählung von Hindernissen."""
    snapshot, assignments = planned
    day = date(2026, 1, 8)
    sick = _absent(planned, day)
    mehrfach = snapshot.model_copy(deep=True)
    for person in mehrfach.employees:
        if person.id == sick:
            continue
        # Gleich mehrere Hürden auf einmal: ausgenommen und ohne Freigabe.
        person.excluded = True
        person.approvals = []

    report = replacement_candidates(mehrfach, assignments, sick, day, day)

    others = len(mehrfach.employees) - 1
    for duty in report["duties"]:
        assert duty["candidates"] == []
        assert sum(duty["blocked"].values()) == others
