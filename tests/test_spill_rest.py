"""Synthetic period-end spill against explicitly configured weekly rest."""

from datetime import date, timedelta

import pytest

from sp5generator.models import Assignment
from sp5generator.solver import solve
from sp5generator.validator import validate
from test_core_rules import case, shift
from test_partial_limits import dated_case
from sp5generator.timeutils import localize


def spill_case(frame="calendar_week"):
    snapshot = case(1, [
        shift("spill", 11, 23, 9), shift("tue", 13, 16, 8),
        shift("thu", 15, 8, 8), shift("sat", 17, 0, 8), shift("sun", 18, 16, 8),
    ])
    snapshot.period_start = snapshot.period_end = date(2026, 1, 11)
    profile = snapshot.profiles[0]
    profile.min_rest_minutes = 660
    profile.weekly_rest_minutes = 2160
    profile.weekly_rest_frame = frame
    snapshot.assignments = [
        Assignment(employee_id="e0", demand_id=d.id, fixed=True)
        for d in snapshot.demands[1:]
    ]
    return snapshot


@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("frame", ["calendar_week", "rolling_elapsed", "rolling_local"])
def test_spill_cannot_remove_36_hour_rest_in_following_week(partial, frame):
    snapshot = spill_case(frame)
    # Following week without the spill: Monday 00 -> Tuesday 16 = 40h free.
    # With spill ending Monday 08: longest gap is 32h. Every pair still has
    # at least the configured 11h daily rest; this is specifically weekly rest.
    proposed = snapshot.assignments + [Assignment(employee_id="e0", demand_id="spill")]
    checked = validate(snapshot, proposed)
    assert not checked.valid
    assert "weekly_rest" in {d.code for d in checked.diagnostics}
    assert not {"rest", "overlap"} & {d.code for d in checked.diagnostics}
    assert validate(snapshot, snapshot.assignments).valid
    result = solve(snapshot, 5, partial=partial)
    if partial:
        assert result.solver_status == "OPTIMAL"
        assert {a.demand_id for a in result.assignments} == {"tue", "thu", "sat", "sun"}
        assert result.validation.valid and not result.validation.complete
    else:
        assert result.solver_status == "INFEASIBLE"


@pytest.mark.parametrize("duration,accepted", [(4, True), (5, True), (6, False)])
def test_calendar_spill_rest_exact_36_hour_boundary(duration, accepted):
    snapshot = spill_case()
    snapshot.shifts[0].segments[0].end = snapshot.shifts[0].segments[0].start + timedelta(hours=duration)
    # Spill ends Monday 03/04/05; next duty starts Tuesday 16 -> 37/36/35h.
    proposed = snapshot.assignments + [Assignment(employee_id="e0", demand_id="spill")]
    assert validate(snapshot, proposed).valid is accepted
    result = solve(snapshot, 5, partial=True)
    assert result.solver_status == "OPTIMAL"
    assert len(result.assignments) == 4 + int(accepted)
    assert result.validation.valid


def test_unselected_spill_does_not_activate_unrelated_future_rest_violation():
    snapshot = spill_case()
    snapshot.shifts[1:] = [
        shift("tue", 13, 8, 8), shift("thu", 15, 0, 8),
        shift("sat", 16, 16, 8), shift("sun", 18, 8, 8),
    ]
    # Future context alone has no gap above 32h. It is not a planning period
    # obligation unless a newly selected planning duty spills into that week.
    assert validate(snapshot, snapshot.assignments).valid
    result = solve(snapshot, 5, partial=True)
    assert result.solver_status == "OPTIMAL"
    assert {a.demand_id for a in result.assignments} == {"tue", "thu", "sat", "sun"}
    assert result.validation.valid


@pytest.mark.parametrize("assigned,active", [(True, True), (False, True), (True, False)])
def test_calendar_spill_rest_respects_profile_assignment_and_validity(assigned, active):
    snapshot = spill_case()
    profile = snapshot.profiles[0]
    future = profile.model_copy(update={
        "id": "future-rest", "valid_from": date(2026, 1, 12 if active else 19),
    })
    profile.weekly_rest_minutes = 0
    snapshot.profiles.append(future)
    if assigned:
        snapshot.employees[0].profile_ids.append(future.id)
    accepted = not (assigned and active)
    proposed = snapshot.assignments + [Assignment(employee_id="e0", demand_id="spill")]
    assert validate(snapshot, proposed).valid is accepted
    result = solve(snapshot, 5, partial=True)
    assert len(result.assignments) == 4 + int(accepted)
    assert result.validation.valid


@pytest.mark.parametrize("sunday", [date(2026, 3, 29), date(2026, 10, 25)])
def test_calendar_spill_rest_uses_vienna_week_after_dst_sunday(sunday):
    times = []
    for offset, start, duration in [(0, 23, 9), (2, 16, 8), (4, 8, 8), (6, 0, 8), (7, 16, 8)]:
        day = sunday + timedelta(days=offset)
        end_day = day + timedelta(days=(start + duration) // 24)
        times.append((localize(day, f"{start:02}:00", "Europe/Vienna"),
                      localize(end_day, f"{(start + duration) % 24:02}:00", "Europe/Vienna")))
    snapshot = dated_case(sunday, sunday, times)
    snapshot.profiles[0].min_rest_minutes = 660
    snapshot.profiles[0].weekly_rest_minutes = 2160
    snapshot.assignments = [Assignment(employee_id="e0", demand_id=str(i), fixed=True) for i in range(1, 5)]
    checked = validate(snapshot, snapshot.assignments + [Assignment(employee_id="e0", demand_id="0")])
    assert not checked.valid
    assert "weekly_rest" in {d.code for d in checked.diagnostics}
    result = solve(snapshot, 5, partial=True)
    assert {a.demand_id for a in result.assignments} == {"1", "2", "3", "4"}
    assert result.validation.valid


@pytest.mark.parametrize("add_daily", [False, True])
def test_spill_does_not_implicitly_add_daily_rest_to_weekly_rest(add_daily):
    snapshot = spill_case()
    snapshot.shifts[0].segments[0].end = snapshot.shifts[0].segments[0].start + timedelta(hours=5)
    snapshot.profiles[0].weekly_rest_add_daily = add_daily
    result = solve(snapshot, 5, partial=True)
    assert result.solver_status == "OPTIMAL"
    assert len(result.assignments) == (4 if add_daily else 5)
    assert result.validation.valid
