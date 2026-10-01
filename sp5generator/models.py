"""Versioned, standalone planning contract. All durations are integer minutes."""
from datetime import date, datetime
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from .security_limits import (
    charge_diagnostic, bounded_planning_records, bounded_normalized_planning,
    bounded_canonical_json, SnapshotWireError,
)

# IDs are opaque: reject overlong values, never strip, normalize or truncate.
MAX_IDENTIFIER_LENGTH = 200
Identifier = Annotated[str, Field(max_length=MAX_IDENTIFIER_LENGTH)]

class Model(BaseModel):
    model_config = ConfigDict(extra='forbid')

    @field_validator('*', mode='before')
    @classmethod
    def bounded_collections(cls, value, info):
        # Reject a long collection before Pydantic expands per-item errors.
        if isinstance(value, (list, tuple)):
            for constraint in cls.model_fields[info.field_name].metadata:
                limit = getattr(constraint, 'max_length', None)
                if limit is not None and len(value) > limit:
                    raise ValueError(f'Collection supports at most {limit} items')
        return value

class Interval(Model):
    start: datetime
    end: datetime

class Qualification(Model):
    id: Identifier
    valid_from: date
    valid_until: date
    level: int = Field(default=1, ge=0)

class Approval(Model):
    function_id: Identifier
    workplace_id: Identifier = Field(description="Exact workplace ID, or * for an explicitly confirmed service-wide approval")
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
    id: Identifier
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
    id: Identifier
    name: str
    # Von der Planung ausgenommen; Daten und Verträge bleiben unverändert.
    excluded: bool = False
    team_ids: list[Identifier] = Field(max_length=1000)
    employment_start: date
    employment_end: date
    approvals: list[Approval] = Field(default_factory=list, max_length=1000)
    qualifications: list[Qualification] = Field(default_factory=list, max_length=1000)
    availability: list[Availability] = Field(default_factory=list, max_length=1000)
    unavailable: list[Interval] = Field(default_factory=list, max_length=1000)
    allowed_kinds: list[str] = Field(default_factory=lambda: ['day','night'], max_length=1000)
    preferred_kind: str | None = None
    preferred_functions: list[Identifier] = Field(default_factory=list, max_length=1000)
    allow_weekends: bool = True
    allow_holidays: bool = True
    profile_ids: list[Identifier] = Field(max_length=1000)
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
    # Harte persönliche Obergrenze für bezahlte Minuten im Planungszeitraum.
    # Leer heißt: keine Grenze aus dieser Person; Regelprofile gelten weiter.
    max_period_minutes: int | None = Field(default=None, ge=0)

class Position(Model):
    id: Identifier
    name: str
    function_id: Identifier
    workplace_id: Identifier
    qualification_ids: list[Identifier] = Field(default_factory=list)
    qualification_level: int = Field(default=1, ge=0)
    qualifications_required: bool

class Shift(Model):
    id: Identifier
    name: str
    kind: str
    team_id: Identifier
    segments: list[Interval]
    paid_minutes: int = Field(ge=0)
    holiday: bool = False
    source: str = 'additional'

class BoundaryWork(Model):
    """Immutable personal work context, not a staffing demand or an approval."""
    id: Identifier
    employee_id: Identifier
    segments: list[Interval]
    kind: Literal['day', 'night', 'unknown'] = 'unknown'
    # Explicit personal work inside the planning period that no staffing demand
    # describes. It blocks the person like any other duty and contributes its
    # stated paid minutes to the period target; it never covers a demand.
    in_period: bool = False
    # A calendar day of personal work the source states without clock times.
    # Set instead of segments: it blocks that day, carries its paid minutes and
    # makes no rest statement, rather than inventing times the source lacks.
    day: date | None = None
    paid_minutes: int = Field(default=0, ge=0)
    holiday: bool = False
    source: str = 'additional'

class Demand(Model):
    id: Identifier
    shift_id: Identifier
    position_id: Identifier
    minimum: int = Field(ge=0)
    maximum: int | None = Field(ge=0, description="Null means no upper staffing limit; zero prohibits staffing")
    # Groups whose source requirements this demand merges; they decide who may
    # staff it. Empty keeps the shift's own team as the only eligible group.
    team_ids: list[Identifier] = Field(default_factory=list)
    # Bedarfe mit derselben Kennung decken denselben Posten ab: erfüllt ist er,
    # sobald sie zusammen die höchste geforderte Mindestbesetzung erreichen.
    # Die Höchstbesetzung bleibt je Bedarf einzeln gültig.
    alternative_group: Identifier | None = None
    source: str = 'additional'

class Assignment(Model):
    employee_id: Identifier
    demand_id: Identifier
    fixed: bool = False
    segments: list[Interval] = Field(default_factory=list)

class Restriction(Model):
    employee_id: Identifier
    shift_id: Identifier
    level: Literal[0,1,2]
    approved: bool = False

class Wish(Model):
    employee_id: Identifier
    shift_id: Identifier
    want: bool
    priority: int = Field(default=1, ge=1, le=1000)

class Objectives(Model):
    # Old saved projects retain their objective unless explicitly enabled.
    workday_transitions: int = Field(default=0, ge=0)
    # Einzelne Arbeitstage nur bei aktiviertem Gewicht bestrafen.
    isolated_days: int = Field(default=0, ge=0)
    # Geteilte Wochenenden nur bei aktiviertem Gewicht bestrafen.
    split_weekends: int = Field(default=0, ge=0)
    # Blocklängenprofil nur bei aktiviertem Gewicht bewerten.
    block_shape: int = Field(default=0, ge=0)
    hours: int = Field(default=1, ge=0)
    # Gleichmäßige Sollerfüllung: nur bei aktiviertem Gewicht bewertet.
    hours_fairness: int = Field(default=0, ge=0)
    # Gleichmäßige Dienstanzahl: nur bei aktiviertem Gewicht bewertet.
    duty_fairness: int = Field(default=0, ge=0)
    nights: int = Field(default=10, ge=0)
    weekends: int = Field(default=10, ge=0)
    holidays: int = Field(default=10, ge=0)
    wishes: int = Field(default=100, ge=0)
    changes: int = Field(default=100, ge=0)

class Snapshot(Model):
    @model_validator(mode='before')
    @classmethod
    def planning_record_budget(cls, value):
        return bounded_planning_records(value)

    @model_validator(mode='after')
    def normalized_planning_budget(self):
        return bounded_normalized_planning(self)

    schema_version: Literal['1.0'] = '1.0'
    id: Identifier
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
    employees: list[Employee] = Field(max_length=1000)
    positions: list[Position] = Field(max_length=2000)
    shifts: list[Shift] = Field(max_length=10000)
    demands: list[Demand] = Field(max_length=20000)
    profiles: list[RuleProfile] = Field(max_length=1000)
    assignments: list[Assignment] = Field(default_factory=list, max_length=5000)
    boundary_work: list[BoundaryWork] = Field(default_factory=list, max_length=5000)
    restrictions: list[Restriction] = Field(default_factory=list, max_length=20000)
    wishes: list[Wish] = Field(default_factory=list, max_length=20000)
    objectives: Objectives = Field(default_factory=Objectives)
    unresolved: list[str] = Field(default_factory=list, max_length=1000)
    metadata: dict = Field(default_factory=dict)

def prepare_snapshot_json(snapshot):
    """Prepare one replayable full value and its exact durable/wire payload.

    Only call at JSON boundaries, never in the native Snapshot constructor:
    optional CSV/XLSX provenance may intentionally contain nonportable labels.
    Reparse fresh fields (not a trusted model identity), then the actual final
    serialized bytes before summaries/SQL or acknowledgement. No sparse dumps.
    """
    bounded_normalized_planning(snapshot)

    def fields(value, mode):
        # Do not let Pydantic turn arbitrary metadata into strings/lists/nulls.
        data = value.model_dump(mode=mode, exclude={'metadata'}, warnings=False)
        data['metadata'] = value.metadata
        return data

    try:
        normalized = Snapshot.model_validate(fields(snapshot, 'python'))
        payload = bounded_canonical_json(fields(normalized, 'json'))
        validated = Snapshot.model_validate_json(payload)
        # A serializer must not silently produce a sparse/coercion-dependent
        # representation different from the validated value returned to callers.
        if bounded_canonical_json(fields(validated, 'json')) != payload:
            raise SnapshotWireError()
        return validated, payload
    except (ValidationError, SnapshotWireError):
        raise
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise SnapshotWireError() from None


class Diagnostic(Model):
    @model_validator(mode='before')
    @classmethod
    def bounded_construction(cls, value):
        return charge_diagnostic(value)

    code: str
    message: str
    employee_id: Identifier | None = None
    demand_id: Identifier | None = None
    date: str | None = None

class Validation(Model):
    valid: bool
    complete: bool
    diagnostics: list[Diagnostic]

class Result(Model):
    schema_version: Literal['1.0'] = '1.0'
    snapshot_id: Identifier
    snapshot_hash: str
    solver_status: Literal['OPTIMAL','FEASIBLE','INFEASIBLE','UNKNOWN','MODEL_INVALID']
    assignments: list[Assignment] = Field(default_factory=list, max_length=5000)
    vacancies: dict[str,int] = Field(default_factory=dict)
    validation: Validation
    runtime_seconds: float
    parameters: dict = Field(default_factory=dict)
    metrics: dict = Field(default_factory=dict)
    objective_value: float | None = None
    best_bound: float | None = None
