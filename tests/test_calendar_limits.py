"""Calendar-boundary and independent personal-limit regressions."""

from datetime import UTC, date, datetime, timedelta
import pytest
from sp5generator.models import (
    Approval,
    Assignment,
    Demand,
    Employee,
    Interval,
    Position,
    RuleProfile,
    Shift,
    Snapshot,
)
from sp5generator.solver import solve
from sp5generator.validator import validate


def sample(day):
    profile = RuleProfile(
        id="r",
        valid_from=day - timedelta(days=10),
        valid_until=day + timedelta(days=10),
        min_rest_minutes=720,
        confirmed=True,
    )
    employee = Employee(
        id="e",
        name="Testperson 001",
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
    shifts = []
    for index in range(2):
        start = datetime.combine(
            day + timedelta(days=index), datetime.min.time(), UTC
        ) + timedelta(hours=8)
        shifts.append(
            Shift(
                id=str(index),
                name="Dienst A",
                kind="day",
                team_id="t",
                segments=[Interval(start=start, end=start + timedelta(hours=4))],
                paid_minutes=240,
            )
        )
    return Snapshot(
        id="boundary",
        revision="1",
        created_at=datetime.now(UTC),
        timezone="UTC",
        period_start=day,
        period_end=day + timedelta(days=1),
        context_start=profile.valid_from,
        context_end=profile.valid_until,
        context_complete=True,
        rule_version="1",
        source="synthetic",
        employees=[employee],
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
            Demand(id=str(i), shift_id=str(i), position_id="p", minimum=1, maximum=1)
            for i in range(2)
        ],
    )


@pytest.mark.parametrize("day", [date(2026, 1, 31), date(2026, 12, 31)])
def test_month_and_year_boundary(day):
    snapshot = sample(day)
    result = solve(snapshot, time_limit=2)
    assert result.validation.complete
    assert len(result.assignments) == 2
    assert validate(snapshot, result.assignments).complete


@pytest.mark.parametrize(
    "limit",
    ["max_daily_minutes", "max_weekly_minutes", "max_period_minutes", "max_work_days"],
)
def test_explicit_limits_cannot_be_paid_away(limit):
    snapshot = sample(date(2026, 1, 5))
    setattr(snapshot.profiles[0], limit, 1)
    snapshot.employees[0].target_minutes = 100000
    result = solve(snapshot, time_limit=2)
    assert result.solver_status == "INFEASIBLE"
    assert not validate(
        snapshot, [Assignment(employee_id="e", demand_id=str(i)) for i in range(2)]
    ).valid


def test_explicit_holiday_and_night_limits():
    snapshot = sample(date(2026, 1, 5))
    snapshot.shifts[0].holiday = True
    snapshot.employees[0].allow_holidays = False
    assert solve(snapshot, time_limit=2).solver_status == "INFEASIBLE"
    snapshot.employees[0].allow_holidays = True
    snapshot.shifts[0].kind = "night"
    snapshot.profiles[0].max_nights = 0
    assert solve(snapshot, time_limit=2).solver_status == "INFEASIBLE"


@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("strict_first", [False, True])
@pytest.mark.parametrize("day,same_week", [(date(2026, 1, 5), True), (date(2026, 1, 4), False)])
def test_dated_profile_switch_preserves_whole_iso_week_limit(partial, strict_first, day, same_week):
    snapshot = sample(day)
    first = snapshot.profiles[0]
    second = first.model_copy(deep=True)
    second.id = "next"
    first.valid_until = day
    second.valid_from = day + timedelta(days=1)
    first.max_weekly_minutes = 240 if strict_first else 480
    second.max_weekly_minutes = 480 if strict_first else 240
    snapshot.profiles.append(second)
    snapshot.employees[0].profile_ids.append(second.id)
    # Eight actual hours, but only two paid: neither paid minutes nor a
    # large target may bypass the four-hour cap during a profile transition.
    snapshot.employees[0].target_minutes = 6000
    for duty in snapshot.shifts:
        duty.paid_minutes = 60
    assignments = [Assignment(employee_id="e", demand_id=str(i)) for i in range(2)]
    checked = validate(snapshot, assignments)
    assert checked.valid is (not same_week)
    weekly = [d for d in checked.diagnostics if d.code == "weekly_limit"]
    assert len(weekly) == int(same_week)
    result = solve(snapshot, time_limit=2, partial=partial)
    if same_week and not partial:
        assert result.solver_status == "INFEASIBLE"
    else:
        assert result.solver_status == "OPTIMAL"
        assert len(result.assignments) == (1 if same_week else 2)
        assert validate(snapshot, result.assignments).valid
        assert sum(result.vacancies.values()) == int(same_week)


@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("coverage", ["missing", "unconfirmed", "confirmed"])
@pytest.mark.parametrize("end_hour", [0, 3])
def test_overnight_spill_requires_confirmed_profile_coverage(partial, coverage, end_hour):
    day = date(2026, 1, 5)
    snapshot = sample(day)
    snapshot.period_end = day
    snapshot.shifts = snapshot.shifts[:1]
    snapshot.demands = snapshot.demands[:1]
    duty = snapshot.shifts[0]
    duty.segments[0].start = datetime(2026, 1, 5, 23, tzinfo=UTC)
    duty.segments[0].end = datetime(2026, 1, 6, end_hour, tzinfo=UTC)
    first = snapshot.profiles[0]
    first.valid_until = day
    if coverage != "missing":
        successor = first.model_copy(update={
            "id": "successor", "valid_from": day + timedelta(days=1),
            "valid_until": snapshot.context_end, "confirmed": coverage == "confirmed",
        })
        snapshot.profiles.append(successor)
        snapshot.employees[0].profile_ids.append(successor.id)
    checked = validate(snapshot, [Assignment(employee_id="e", demand_id="0")])
    accepted = coverage == "confirmed" or end_hour == 0
    assert checked.valid is accepted
    assert ("profile" in {d.code for d in checked.diagnostics}) is (not accepted)
    result = solve(snapshot, time_limit=2, partial=partial)
    if accepted or partial:
        assert result.solver_status == "OPTIMAL"
        assert len(result.assignments) == int(accepted)
        assert result.validation.valid
    else:
        assert result.solver_status == "INFEASIBLE"
