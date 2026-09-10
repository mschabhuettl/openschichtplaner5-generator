"""Fresh synthetic examples; no external data source."""

from datetime import UTC, date, datetime, timedelta
from .models import (
    Approval,
    Assignment,
    Availability,
    Demand,
    Employee,
    Interval,
    Position,
    RuleProfile,
    Shift,
    Snapshot,
    Wish,
)


def make_demo(
    employees: int = 12, days: int = 14, impossible: bool = False
) -> Snapshot:
    start = date(2026, 1, 5)
    end = start + timedelta(days=days - 1)
    context_start, context_end = start - timedelta(days=8), end + timedelta(days=8)
    profile = RuleProfile(
        id="example",
        valid_from=context_start,
        valid_until=context_end,
        min_rest_minutes=720,
        weekly_rest_minutes=2160,
        max_consecutive_work_days=6,
        max_consecutive_nights=3,
        max_weekly_minutes=2400,
        confirmed=True,
        source="synthetic",
    )
    positions = [
        Position(
            id=f"p{i}",
            name=f"Funktion {chr(65 + i)}",
            function_id=f"f{i}",
            workplace_id=f"w{i}",
            qualifications_required=False,
        )
        for i in range(2)
    ]
    people = []
    for i in range(employees):
        part_time = i % 4 == 0
        availability = []
        if i == 0:
            availability = [
                Availability(
                    valid_from=start,
                    valid_until=end,
                    weekdays=[0, 1, 2, 3],
                    start_time="08:00",
                    end_time="13:00",
                    source="synthetic",
                )
            ]
        elif i == 1:
            availability = [
                Availability(
                    valid_from=start,
                    valid_until=end,
                    cycle_anchor=start,
                    cycle_weeks=2,
                    cycle_phase=phase,
                    weekdays=([0, 1, 2, 3, 4] if phase == 0 else [1, 2, 3, 4, 5]),
                )
                for phase in range(2)
            ]
        people.append(
            Employee(
                id=f"e{i:03}",
                name=f"Testperson {i + 1:03}",
                team_ids=["team-a"],
                employment_start=context_start,
                employment_end=context_end,
                approvals=[
                    Approval(
                        function_id=p.function_id,
                        workplace_id=p.workplace_id,
                        valid_from=context_start,
                        valid_until=context_end,
                    )
                    for p in positions
                    if i % 3 != 0 or p.id == "p0"
                ],
                availability=availability,
                profile_ids=["example"],
                allowed_kinds=["day"] if i == 0 else ["day", "night"],
                preferred_kind="night" if i == 2 else None,
                target_minutes=(days // 7) * (1200 if part_time else 2400),
                employment_fraction=50 if part_time else 100,
                unavailable=[
                    Interval(
                        start=datetime.combine(
                            start + timedelta(days=2), datetime.min.time(), UTC
                        ),
                        end=datetime.combine(
                            start + timedelta(days=3), datetime.min.time(), UTC
                        ),
                    )
                ]
                if i == 3
                else [],
            )
        )
    shifts, demands = [], []
    for day_no in range(days):
        day = start + timedelta(days=day_no)
        for k, hour, length in [("day", 8, 5), ("night", 20, 10)]:
            shift_id = f"s{day_no}-{k}"
            begin = datetime(day.year, day.month, day.day, hour, tzinfo=UTC)
            shifts.append(
                Shift(
                    id=shift_id,
                    name="Dienst A" if k == "day" else "Dienst B",
                    kind=k,
                    team_id="team-a",
                    segments=[
                        Interval(start=begin, end=begin + timedelta(hours=length))
                    ],
                    paid_minutes=length * 60,
                    source="synthetic",
                )
            )
            for p in positions:
                n = max(1, employees // 12)
                if impossible and day_no == 0 and k == "day":
                    n = employees + 1
                demands.append(
                    Demand(
                        id=f"d{day_no}-{k}-{p.id}",
                        shift_id=shift_id,
                        position_id=p.id,
                        minimum=n,
                        maximum=n,
                        source="synthetic",
                    )
                )
    return Snapshot(
        id="synthetic-example",
        revision="1",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        timezone="UTC",
        period_start=start,
        period_end=end,
        context_start=context_start,
        context_end=context_end,
        context_complete=True,
        rule_version="synthetic-1",
        source="synthetic",
        employees=people,
        positions=positions,
        shifts=shifts,
        demands=demands,
        profiles=[profile],
        assignments=[Assignment(employee_id="e000", demand_id="d0-day-p0", fixed=True)],
        wishes=[
            Wish(
                employee_id="e002",
                shift_id=f"s{min(1, days - 1)}-night",
                want=True,
                priority=10,
            )
        ],
        metadata={
            "description": "Independently constructed synthetic example. Context outside period explicitly empty."
        },
    )
