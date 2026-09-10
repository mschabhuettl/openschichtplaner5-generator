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
