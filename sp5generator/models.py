"""Versioned, standalone planning contract. All durations are integer minutes."""
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class Model(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Interval(Model):
    start: datetime
    end: datetime

class Qualification(Model):
    id: str
    valid_from: date
    valid_until: date
    level: int = Field(default=1, ge=0)

class Approval(Model):
    function_id: str
    workplace_id: str = Field(description="Exact workplace ID, or * for an explicitly confirmed service-wide approval")
    valid_from: date
    valid_until: date
    supervised: bool = False

class Availability(Model):
    valid_from: date
    valid_until: date
    weekdays: list[int] = Field(default_factory=lambda: list(range(7)))
    start_time: str = '00:00'
    end_time: str = '24:00'
    cycle_anchor: date | None = None
    cycle_weeks: int = Field(default=1, ge=1)
    cycle_phase: int = Field(default=0, ge=0)
    source: str = 'additional'

class RuleProfile(Model):
    id: str
    version: str = '1'
    valid_from: date
    valid_until: date
    min_rest_minutes: int = Field(ge=0)
    after_night_rest_minutes: int = Field(default=0, ge=0)
    after_night_block_rest_minutes: int = Field(default=0, ge=0)
    night_block_gap_days: int = Field(default=1, ge=1)
    max_consecutive_work_days: int | None = Field(default=None, ge=1)
    max_consecutive_nights: int | None = Field(default=None, ge=1)
    max_daily_minutes: int | None = Field(default=None, ge=0)
    max_weekly_minutes: int | None = Field(default=None, ge=0)
    max_period_minutes: int | None = Field(default=None, ge=0)
    max_work_days: int | None = Field(default=None, ge=0)
    max_nights: int | None = Field(default=None, ge=0)
    max_weekends: int | None = Field(default=None, ge=0)
    weekly_rest_minutes: int = Field(default=0, ge=0)
    weekly_rest_frame: Literal['calendar_week','rolling_elapsed','rolling_local'] = 'calendar_week'
    weekly_rest_window_days: int = Field(default=7, ge=1)
    weekly_rest_add_daily: bool = False
    confirmed: bool = False
    source: str = 'additional'

class Employee(Model):
    id: str
    name: str
    team_ids: list[str]
    employment_start: date
    employment_end: date
    approvals: list[Approval] = Field(default_factory=list)
    qualifications: list[Qualification] = Field(default_factory=list)
    availability: list[Availability] = Field(default_factory=list)
    unavailable: list[Interval] = Field(default_factory=list)
    allowed_kinds: list[str] = Field(default_factory=lambda: ['day','night'])
    preferred_kind: str | None = None
    preferred_functions: list[str] = Field(default_factory=list)
    allow_weekends: bool = True
    allow_holidays: bool = True
    profile_ids: list[str]
    target_minutes: int = Field(default=0, ge=0)
    # Contractual weekly workload: soft distribution goal, never a hard limit.
    contractual_weekly_minutes: int | None = Field(default=None, ge=0, strict=True)
    balance_minutes: int = 0
    credit_minutes: int = Field(default=0, ge=0)
    employment_fraction: int = Field(default=100, ge=1, le=100)
    historical_nights: int = Field(default=0, ge=0)
    historical_weekends: int = Field(default=0, ge=0)
    historical_holidays: int = Field(default=0, ge=0)
    mentor_capacity: int = Field(default=0, ge=0)

class Position(Model):
    id: str
    name: str
    function_id: str
    workplace_id: str
    qualification_ids: list[str] = Field(default_factory=list)
    qualification_level: int = Field(default=1, ge=0)
    qualifications_required: bool

class Shift(Model):
    id: str
    name: str
    kind: str
    team_id: str
    segments: list[Interval]
    paid_minutes: int = Field(ge=0)
    holiday: bool = False
    source: str = 'additional'

class BoundaryWork(Model):
    """Immutable personal work context, not a staffing demand or an approval."""
    id: str
    employee_id: str
    segments: list[Interval]
    kind: Literal['day', 'night', 'unknown'] = 'unknown'
    source: str = 'additional'

class Demand(Model):
    id: str
    shift_id: str
    position_id: str
    minimum: int = Field(ge=0)
    maximum: int | None = Field(ge=0, description="Null means no upper staffing limit; zero prohibits staffing")
    # Groups whose source requirements this demand merges; they decide who may
    # staff it. Empty keeps the shift's own team as the only eligible group.
    team_ids: list[str] = Field(default_factory=list)
    source: str = 'additional'

class Assignment(Model):
    employee_id: str
    demand_id: str
    fixed: bool = False
    segments: list[Interval] = Field(default_factory=list)

class Restriction(Model):
    employee_id: str
    shift_id: str
    level: Literal[0,1,2]
    approved: bool = False

class Wish(Model):
    employee_id: str
    shift_id: str
    want: bool
    priority: int = Field(default=1, ge=1, le=1000)

class Objectives(Model):
    # Old saved projects retain their objective unless explicitly enabled.
    workday_transitions: int = Field(default=0, ge=0)
    hours: int = Field(default=1, ge=0)
    nights: int = Field(default=10, ge=0)
    weekends: int = Field(default=10, ge=0)
    holidays: int = Field(default=10, ge=0)
    wishes: int = Field(default=100, ge=0)
    changes: int = Field(default=100, ge=0)

class Snapshot(Model):
    schema_version: Literal['1.0'] = '1.0'
    id: str
    revision: str
    created_at: datetime
    timezone: str
    period_start: date
    period_end: date
    context_start: date
    context_end: date
    context_complete: bool = False
    rule_version: str
    software_versions: dict[str,str] = Field(default_factory=dict)
    source: Literal['synthetic','sp5','json']
    employees: list[Employee]
    positions: list[Position]
    shifts: list[Shift]
    demands: list[Demand]
    profiles: list[RuleProfile]
    assignments: list[Assignment] = Field(default_factory=list)
    boundary_work: list[BoundaryWork] = Field(default_factory=list)
    restrictions: list[Restriction] = Field(default_factory=list)
    wishes: list[Wish] = Field(default_factory=list)
    objectives: Objectives = Field(default_factory=Objectives)
    unresolved: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

class Diagnostic(Model):
    code: str
    message: str
    employee_id: str | None = None
    demand_id: str | None = None
    date: str | None = None

class Validation(Model):
    valid: bool
    complete: bool
    diagnostics: list[Diagnostic]

class Result(Model):
    schema_version: Literal['1.0'] = '1.0'
    snapshot_id: str
    snapshot_hash: str
    solver_status: Literal['OPTIMAL','FEASIBLE','INFEASIBLE','UNKNOWN','MODEL_INVALID']
    assignments: list[Assignment] = Field(default_factory=list)
    vacancies: dict[str,int] = Field(default_factory=dict)
    validation: Validation
    runtime_seconds: float
    parameters: dict = Field(default_factory=dict)
    metrics: dict = Field(default_factory=dict)
    objective_value: float | None = None
    best_bound: float | None = None
