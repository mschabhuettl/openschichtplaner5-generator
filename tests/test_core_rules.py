from datetime import UTC, date, datetime, timedelta
from itertools import product
from zoneinfo import ZoneInfo
import pytest
from sp5generator.models import (
    RuleProfile,
    Employee,
    Approval,
    Snapshot,
    Position,
    Demand,
    Shift,
    Interval,
    Assignment,
    Restriction,
    Qualification,
    Availability,
    Objectives,
)
from sp5generator.solver import solve
from sp5generator.validator import validate, weekly_windows
from sp5generator.timeutils import availability_window, localize, minute, longest_free
from sp5generator.domain import input_diagnostics, maximum_matching


def case(n=2, shifts=None):
    day = date(2026, 1, 5)
    profile = RuleProfile(
        id="r",
        valid_from=day - timedelta(days=10),
        valid_until=day + timedelta(days=20),
        min_rest_minutes=720,
        confirmed=True,
    )
    people = [
        Employee(
            id=f"e{i}",
            name=f"Testperson {i + 1:03}",
            team_ids=["t"],
            employment_start=profile.valid_from,
            employment_end=profile.valid_until,
            profile_ids=["r"],
            approvals=[
                Approval(
                    function_id="f",
                    workplace_id="w",
                    valid_from=profile.valid_from,
                    valid_until=profile.valid_until,
                )
            ],
        )
        for i in range(n)
    ]
    shifts = shifts or [shift("s", 5, 8, 8)]
    return Snapshot(
        id="test",
        revision="1",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        timezone="UTC",
        period_start=day,
        period_end=day + timedelta(days=6),
        context_start=profile.valid_from,
        context_end=profile.valid_until,
        context_complete=True,
        rule_version="1",
        source="synthetic",
        employees=people,
        profiles=[profile],
        positions=[
            Position(
                id="p",
                name="Funktion A",
                function_id="f",
                workplace_id="w",
                qualifications_required=False,
            )
        ],
        shifts=shifts,
        demands=[
            Demand(id=s.id, shift_id=s.id, position_id="p", minimum=1, maximum=1)
            for s in shifts
        ],
    )


def shift(id, day, hour, length, kind="day"):
    a = datetime(2026, 1, day, hour, tzinfo=UTC)
    return Shift(
        id=id,
        name="Dienst A",
        kind=kind,
        team_id="t",
        segments=[Interval(start=a, end=a + timedelta(hours=length))],
        paid_minutes=int(length * 60),
    )


def assignment(e="e0", d="s"):
    return Assignment(employee_id=e, demand_id=d)


def test_complete_and_independent_corruption():
    s = case()
    r = solve(s, 2)
    assert r.solver_status == "OPTIMAL" and r.validation.complete
    assert not validate(s, r.assignments + r.assignments).valid
    s.employees[int(r.assignments[0].employee_id[1:])].approvals = []
    assert not validate(s, r.assignments).valid


@pytest.mark.parametrize(
    "level,approved,expected",
    [(0, False, True), (1, False, False), (1, True, True), (2, True, False)],
)
def test_restrictions(level, approved, expected):
    s = case(1)
    s.restrictions = [
        Restriction(employee_id="e0", shift_id="s", level=level, approved=approved)
    ]
    assert (solve(s, 2).solver_status == "OPTIMAL") == expected


@pytest.mark.parametrize("delta,expected", [(-1, False), (0, True), (1, True)])
def test_exact_rest(delta, expected):
    s = case(1, [shift("a", 5, 23, 8, "night"), shift("b", 6, 19, 2)])
    s.shifts[1].segments[0].start += timedelta(minutes=delta)
    assert validate(s, [assignment(d="a"), assignment(d="b")]).valid == expected
    assert (solve(s, 2).solver_status == "OPTIMAL") == expected


def test_qualification_expiry_and_explicit_none():
    s = case(1)
    s.positions[0].qualifications_required = True
    s.positions[0].qualification_ids = ["q"]
    assert solve(s, 2).solver_status == "INFEASIBLE"
    s.employees[0].qualifications = [
        Qualification(id="q", valid_from=date(2026, 1, 1), valid_until=date(2026, 1, 4))
    ]
    assert solve(s, 2).solver_status == "INFEASIBLE"
    s.employees[0].qualifications[0].valid_until = date(2026, 1, 5)
    assert solve(s, 2).validation.complete


def test_parent_window_whole_shift_and_rotating_phase():
    s = case(1, [shift("s", 5, 8, 5)])
    e = s.employees[0]
    e.availability = [
        Availability(
            valid_from=date(2026, 1, 1),
            valid_until=date(2026, 2, 1),
            weekdays=[0, 1, 2, 3],
            start_time="08:00",
            end_time="13:00",
            cycle_anchor=date(2026, 1, 5),
            cycle_weeks=2,
            cycle_phase=0,
        )
    ]
    assert solve(s, 2).validation.complete
    s.shifts[0].segments[0].end += timedelta(minutes=1)
    assert solve(s, 2).solver_status == "INFEASIBLE"
    s.shifts[0].segments[0].end -= timedelta(minutes=1)
    e.availability[0].cycle_phase = 1
    assert solve(s, 2).solver_status == "INFEASIBLE"


def test_absence_split_and_multiple_nonoverlap_duties():
    s = case(1, [shift("a", 5, 8, 2), shift("b", 5, 12, 2)])
    s.profiles[0].min_rest_minutes = 120
    assert solve(s, 2).validation.complete
    s.employees[0].unavailable = [
        Interval(
            start=datetime(2026, 1, 5, 9, tzinfo=UTC),
            end=datetime(2026, 1, 5, 10, tzinfo=UTC),
        )
    ]
    assert solve(s, 2).solver_status == "INFEASIBLE"
    s.employees[0].unavailable = []
    s.shifts[0].segments.append(
        Interval(
            start=datetime(2026, 1, 5, 15, tzinfo=UTC),
            end=datetime(2026, 1, 5, 16, tzinfo=UTC),
        )
    )
    assert not validate(s, [assignment(d="a"), assignment(d="b")]).valid


def test_candidate_pool_double_count_and_partial():
    s = case(2)
    s.demands.extend(
        [
            Demand(id="b", shift_id="s", position_id="p", minimum=1, maximum=1),
            Demand(id="c", shift_id="s", position_id="p", minimum=1, maximum=1),
        ]
    )
    assert solve(s, 2).solver_status == "INFEASIBLE"
    r = solve(s, 2, partial=True)
    assert (
        r.validation.valid
        and not r.validation.complete
        and sum(r.vacancies.values()) == 1
    )


def test_only_night_vs_preferred():
    s = case(1)
    s.employees[0].preferred_kind = "night"
    assert solve(s, 2).validation.complete
    s.employees[0].allowed_kinds = ["night"]
    assert solve(s, 2).solver_status == "INFEASIBLE"


def test_paid_target_not_maximum():
    s = case(1)
    s.employees[0].target_minutes = 60
    r = solve(s, 2)
    assert (
        r.validation.complete
        and r.metrics["employees"]["e0"]["deviation_minutes"] == 420
    )
    s.profiles[0].max_daily_minutes = 479
    assert solve(s, 2).solver_status == "INFEASIBLE"


def test_fixed_ineligible_and_unknown():
    s = case(1)
    s.assignments = [Assignment(employee_id="e0", demand_id="s", fixed=True)]
    assert not validate(s, []).valid
    s.employees[0].allowed_kinds = ["night"]
    assert solve(s, 2).solver_status == "INFEASIBLE"
    assert solve(case(), 0).solver_status == "UNKNOWN"
    s = case()
    s.demands[0].maximum = 0
    assert solve(s, 2).solver_status == "MODEL_INVALID"


def test_dst_elapsed_and_ambiguous():
    with pytest.raises(ValueError, match="Nicht existierende"):
        localize(date(2026, 3, 29), "02:30", "Europe/Berlin")
    with pytest.raises(ValueError, match="Mehrdeutige"):
        localize(date(2026, 10, 25), "02:30", "Europe/Berlin")
    assert (
        minute(localize(date(2026, 10, 25), "02:30", "Europe/Berlin", 1))
        - minute(localize(date(2026, 10, 25), "02:30", "Europe/Berlin", 0))
        == 60
    )
    assert (
        minute(localize(date(2026, 3, 29), "04:00", "Europe/Berlin"))
        - minute(localize(date(2026, 3, 29), "00:00", "Europe/Berlin"))
        == 180
    )


def test_weekly_rest_additive_and_context():
    s = case(
        1,
        [
            shift("a", 5, 0, 24),
            shift("b", 7, 12, 24),
            shift("c", 9, 0, 24),
            shift("d", 11, 0, 24),
        ],
    )
    s.profiles[0].weekly_rest_minutes = 2160
    assignments = [assignment(d=x.id) for x in s.shifts]
    assert validate(s, assignments).complete
    s.profiles[0].weekly_rest_add_daily = True
    assert not validate(s, assignments).valid
    s.profiles[0].weekly_rest_add_daily = False
    s.context_complete = False
    assert validate(s, assignments).valid and not validate(s, assignments).complete


def test_rolling_critical_boundaries_match_exhaustive_minutes():
    s = case(1)
    p = s.profiles[0]
    p.weekly_rest_frame = "rolling_elapsed"
    p.weekly_rest_window_days = 1
    p.weekly_rest_minutes = 180
    s.period_end = s.period_start
    base = minute(datetime(2026, 1, 5, tzinfo=UTC))
    for offsets in [(0, 300, 900), (100, 700, 1300), (0, 500, 1000)]:
        spans = [(base + i, base + i + 180) for i in offsets]
        critical = all(
            longest_free(spans, a, b) >= r for a, b, r in weekly_windows(s, p, spans)
        )
        brute = all(
            longest_free(spans, a, a + 1440) >= 180
            for a in range(base - 1439, base + 1440)
        )
        assert critical == brute


def test_small_exhaustive_optimum():
    s = case(2, [shift("a", 5, 8, 8), shift("b", 6, 8, 8)])
    s.objectives = Objectives(
        hours=1, nights=0, weekends=0, holidays=0, wishes=0, changes=0
    )
    s.employees[0].target_minutes = 960
    s.employees[1].target_minutes = 0
    reference = []
    for choice in product(range(2), repeat=2):
        plan = [assignment("e" + str(e), d) for e, d in zip(choice, ["a", "b"])]
        if validate(s, plan).complete:
            cost = sum(
                abs(choice.count(e) * 480 - s.employees[e].target_minutes)
                for e in range(2)
            )
            reference.append(cost)
    r = solve(s, 2)
    assert r.solver_status == "OPTIMAL" and r.objective_value == min(reference)


def test_mentoring_real_capacity():
    s = case(3)
    s.demands[0].minimum = s.demands[0].maximum = 3
    for e in s.employees[:2]:
        e.approvals[0].supervised = True
    s.employees[2].mentor_capacity = 1
    assert solve(s, 2).solver_status == "INFEASIBLE"
    s.employees[2].mentor_capacity = 2
    r = solve(s, 2)
    assert r.validation.complete
    s.employees[2].mentor_capacity = 1
    assert not validate(s, r.assignments).valid


def test_arbitrary_data_defined_positions():
    s = case(1)
    s.positions[0].function_id = "function-random-43"
    s.positions[0].workplace_id = "workplace-random-11"
    s.employees[0].approvals[0].function_id = s.positions[0].function_id
    s.employees[0].approvals[0].workplace_id = s.positions[0].workplace_id
    assert solve(s, 2).validation.complete


def test_next_period_consecutive_context_and_intervals():
    s = case(1, [shift("a", 11, 8, 8), shift("b", 12, 8, 8), shift("c", 13, 8, 8)])
    s.profiles[0].max_consecutive_work_days = 2
    s.assignments = [
        Assignment(employee_id="e0", demand_id=d, fixed=True) for d in ["b", "c"]
    ]
    assert solve(s, 2).solver_status == "INFEASIBLE"
    assert not validate(s, [assignment(d=d) for d in ["a", "b", "c"]]).valid
    s = case(1)
    r = solve(s, 2)
    assert r.assignments[0].segments
    r.assignments[0].segments = [
        Interval(
            start=datetime(2026, 1, 5, 9, tzinfo=UTC),
            end=datetime(2026, 1, 5, 10, tzinfo=UTC),
        )
    ]
    assert not validate(s, r.assignments).valid


def test_context_horizon_and_night_block_extra():
    s = case(1)
    s.context_start = s.period_start
    s.context_end = s.period_end
    r = solve(s, 2)
    assert r.validation.valid and not r.validation.complete
    s = case(
        1,
        [
            shift("a", 5, 20, 10, "night"),
            shift("b", 6, 20, 10, "night"),
            shift("c", 7, 20, 2),
        ],
    )
    s.profiles[0].after_night_block_rest_minutes = 24 * 60
    assert solve(s, 2).solver_status == "INFEASIBLE"


def test_solver_offline(monkeypatch):
    import socket

    def reject(*args, **kwargs):
        raise AssertionError("External network connection attempted")

    monkeypatch.setattr(socket.socket, "connect", reject)
    monkeypatch.setattr(socket, "create_connection", reject)
    assert solve(case(), 2).validation.complete


def test_expired_profile_does_not_constrain_new_series():
    s = case(1, [shift("a", 6, 8, 8), shift("b", 7, 8, 8)])
    s.profiles[0].max_consecutive_work_days = 1
    s.profiles[0].valid_until = date(2026, 1, 5)
    new = s.profiles[0].model_copy(deep=True)
    new.id = "r2"
    new.valid_from = date(2026, 1, 6)
    new.valid_until = s.context_end
    new.max_consecutive_work_days = None
    s.profiles.append(new)
    s.employees[0].profile_ids.append("r2")
    assert solve(s, 2).validation.complete


def test_additive_rest_combines_simultaneous_profiles():
    s = case(
        1,
        [
            shift("a", 5, 0, 24),
            shift("b", 7, 12, 24),
            shift("c", 9, 0, 24),
            shift("d", 11, 0, 24),
        ],
    )
    p = s.profiles[0].model_copy(deep=True)
    p.id = "weekly"
    p.min_rest_minutes = 0
    p.weekly_rest_minutes = 2160
    p.weekly_rest_add_daily = True
    s.profiles.append(p)
    s.employees[0].profile_ids.append("weekly")
    assert not validate(s, [assignment(d=d.id) for d in s.demands]).valid
    assert solve(s, 2).solver_status == "INFEASIBLE"


def test_night_block_bridge_is_not_false_pair_conflict():
    s = case(
        1,
        [
            shift("a", 5, 22, 8, "night"),
            shift("b", 6, 22, 8, "night"),
            shift("c", 7, 22, 8, "night"),
        ],
    )
    s.profiles[0].after_night_block_rest_minutes = 2880
    assert solve(s, 2).validation.complete
    assert validate(s, [assignment(d=d.id) for d in s.demands]).complete
    s.demands[1].minimum = s.demands[1].maximum = 0
    assert solve(s, 2).solver_status == "INFEASIBLE"


def test_creation_timestamp_can_have_subminute_precision():
    s = case()
    s.created_at = datetime(2026, 1, 1, 10, 20, 33, 123456, tzinfo=UTC)
    assert solve(s, 2).validation.complete


def test_future_profile_limit_checks_context_series():
    s = case(1, [shift("a", 11, 8, 8), shift("b", 12, 8, 8)])
    future = s.profiles[0].model_copy(deep=True)
    future.id = "future"
    future.valid_from = date(2026, 1, 12)
    future.max_consecutive_work_days = 1
    s.profiles.append(future)
    s.employees[0].profile_ids.append("future")
    s.assignments = [Assignment(employee_id="e0", demand_id="b", fixed=True)]
    assert not validate(s, [assignment(d="a"), assignment(d="b")]).valid
    assert solve(s, 2).solver_status == "INFEASIBLE"


def test_service_wide_approval_preserves_service_boundary_and_qualification():
    s = case(n=1)
    s.employees[0].approvals[0].workplace_id = '*'
    s.positions[0].workplace_id = 'another-physical-place'
    result = solve(s, time_limit=5)
    assert result.validation.complete
    assert validate(s, result.assignments).complete
    s.positions[0].function_id = 'other-service'
    assert not validate(s, result.assignments).valid
    assert not solve(s, time_limit=5).validation.complete
    s.positions[0].function_id = 'f'
    s.positions[0].qualifications_required = True
    s.positions[0].qualification_ids = ['qualification-a']
    assert not validate(s, result.assignments).valid


def test_service_wide_supervised_approval_still_needs_mentor():
    s = case(n=1)
    s.employees[0].approvals[0].workplace_id = '*'
    s.employees[0].approvals[0].supervised = True
    assert not solve(s, time_limit=5).validation.complete
    assert not validate(s, [Assignment(employee_id='e0', demand_id=s.demands[0].id)]).valid


def test_unbounded_maximum_is_distinct_from_zero():
    s = case(n=2)
    s.demands[0].minimum = 2
    s.demands[0].maximum = None
    result = solve(s, time_limit=5)
    assert result.validation.complete and len(result.assignments) == 2
    s.demands[0].minimum = 0
    s.demands[0].maximum = 0
    assert not validate(s, result.assignments).valid
    zero = solve(s, time_limit=5)
    assert zero.validation.complete and zero.assignments == []


@pytest.mark.parametrize("category", ["nights", "weekends", "holidays"])
def test_fairness_cannot_make_multi_person_demand_infeasible(category):
    duty = shift("s", 10 if category == "weekends" else 5, 8, 8,
                 "night" if category == "nights" else "day")
    duty.holiday = category == "holidays"
    s = case(3, [duty])
    s.demands[0].minimum = s.demands[0].maximum = 3
    for employee in s.employees[1:]:
        employee.employment_fraction = 1
    s.objectives = Objectives(hours=0, nights=0, weekends=0, holidays=0,
                              wishes=0, changes=0)
    setattr(s.objectives, category, 1)
    assert validate(s, [assignment(e.id) for e in s.employees]).complete
    result = solve(s, 2)
    assert result.validation.complete
    assert result.solver_status == "OPTIMAL"
    # One actual burden each; opportunity shares are 100/102, 1/102, 1/102.
    expected = sum(100 * abs(102 - 3 * share) // 102 for share in (100, 1, 1))
    assert result.metrics["objective_contributions"][category] == expected


def test_weekend_limit_counts_only_profile_active_days():
    s = case(1, [shift("s", 10, 8, 8)])
    p = s.profiles[0].model_copy(deep=True)
    p.id = "sunday"
    p.valid_from = p.valid_until = date(2026, 1, 11)
    p.max_weekends = 0
    s.profiles.append(p)
    s.employees[0].profile_ids.append(p.id)
    assert validate(s, [assignment()]).complete
    assert solve(s, 2).validation.complete


def test_weekend_fairness_excludes_fixed_context_duties():
    s = case(2, [shift("before", 3, 8, 8), shift("s", 10, 8, 8)])
    s.assignments = [Assignment(employee_id="e0", demand_id="before", fixed=True)]
    s.objectives = Objectives(hours=0, nights=0, weekends=1, holidays=0,
                              wishes=0, changes=0)
    result = solve(s, 2)
    assert result.validation.complete
    assert sum(e["weekends"] for e in result.metrics["employees"].values()) == 1
    assert result.metrics["objective_contributions"]["weekends"] == 100


def test_night_metrics_count_start_days_not_multiple_duties():
    s = case(1, [shift("a", 5, 0, 2, "night"), shift("b", 5, 4, 2, "night")])
    s.profiles[0].min_rest_minutes = 0
    s.profiles[0].max_nights = 1
    result = solve(s, 2)
    assert result.validation.complete
    assert result.metrics["employees"]["e0"]["nights"] == 1


def test_validator_rejects_new_assignment_outside_planning_period():
    s = case(1, [shift("context", 12, 8, 8)])
    s.demands[0].minimum = 0
    checked = validate(s, [assignment(d="context")])
    assert not checked.valid
    assert any(d.code == "context_assignment" for d in checked.diagnostics)
    s.assignments = [Assignment(employee_id="e0", demand_id="context", fixed=True)]
    assert validate(s, s.assignments).complete


@pytest.mark.parametrize(
    "start,end,weekdays,expected_valid",
    [
        (date(2026, 3, 28), date(2026, 3, 29), [5], False),
        (date(2026, 10, 24), date(2026, 10, 25), [5], False),
        (date(2026, 3, 29), date(2026, 3, 30), [6], True),
        (date(2026, 3, 28), date(2026, 3, 28), [5], True),
    ],
)
def test_overnight_availability_validates_actual_end_date(start, end, weekdays, expected_valid):
    s = case(1)
    s.timezone = "Europe/Berlin"
    s.context_end = date(2026, 11, 1)
    availability = Availability(valid_from=start, valid_until=end, weekdays=weekdays,
                                start_time="22:00", end_time="02:30")
    s.employees[0].availability = [availability]
    assert (not input_diagnostics(s)) == expected_valid
    if not expected_valid:
        assert solve(s, 2).solver_status == "MODEL_INVALID"
    elif start == end:
        a, b = availability_window(start, availability, s.timezone)
        assert b - a == 120


def test_inactive_alternating_week_does_not_resolve_nonexistent_clock():
    s = case(1)
    s.timezone = "Europe/Berlin"
    s.context_end = date(2026, 4, 1)
    s.employees[0].availability = [Availability(
        valid_from=date(2026, 3, 29), valid_until=date(2026, 3, 29),
        weekdays=[6], start_time="02:30", end_time="04:00",
        cycle_anchor=date(2026, 3, 23), cycle_weeks=2, cycle_phase=1,
    )]
    assert input_diagnostics(s) == []


def test_indefinitely_valid_availability_and_rolling_profile():
    s = case(1)
    s.employees[0].availability = [Availability(valid_from=date.min, valid_until=date.max)]
    s.profiles[0].valid_from = date.min
    s.profiles[0].valid_until = date.max
    s.profiles[0].weekly_rest_frame = "rolling_elapsed"
    s.profiles[0].weekly_rest_minutes = 1440
    assert solve(s, 2).validation.complete


def test_localize_rejects_invalid_fold_even_for_unambiguous_clock():
    with pytest.raises(ValueError, match="fold"):
        localize(date(2026, 1, 5), "12:00", "Europe/Berlin", fold=2)


def test_candidate_matching_handles_thousand_position_augmenting_path():
    adjacency = {i: [i, i + 1] for i in range(1000)}
    adjacency[1000] = [0]
    matching = maximum_matching(adjacency)
    assert len(matching) == len(adjacency)
    assert len(set(matching.values())) == len(adjacency)
    assert all(right in adjacency[left] for right, left in matching.items())


def test_supported_thousand_employee_pool_does_not_exceed_recursion_limit():
    s = case(1000)
    s.demands[0].minimum = s.demands[0].maximum = 1000
    assert input_diagnostics(s) == []
    assert solve(s, 0.01).solver_status in {"UNKNOWN", "FEASIBLE", "OPTIMAL"}


def test_result_interval_comparison_uses_actual_instant_during_dst_fold():
    s = case(1)
    s.timezone = "Europe/Berlin"
    s.period_start = s.period_end = date(2026, 10, 25)
    s.context_start, s.context_end = date(2026, 10, 1), date(2026, 11, 10)
    s.profiles[0].valid_from, s.profiles[0].valid_until = s.context_start, s.context_end
    employee = s.employees[0]
    employee.employment_start, employee.employment_end = s.context_start, s.context_end
    employee.approvals[0].valid_from = s.context_start
    employee.approvals[0].valid_until = s.context_end
    tz = ZoneInfo(s.timezone)
    start = datetime(2026, 10, 25, 2, 10, tzinfo=tz, fold=0)
    end = datetime(2026, 10, 25, 2, 40, tzinfo=tz, fold=0)
    s.shifts[0].segments = [Interval(start=start, end=end)]
    proposal = assignment()
    proposal.segments = [Interval(start=start.replace(fold=1), end=end.replace(fold=1))]
    checked = validate(s, [proposal])
    assert not checked.valid
    assert any(d.code == "interval_mismatch" for d in checked.diagnostics)
    proposal.segments = [Interval(start=start.astimezone(UTC), end=end.astimezone(UTC))]
    assert validate(s, [proposal]).complete
