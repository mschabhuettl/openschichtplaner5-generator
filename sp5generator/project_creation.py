"""Build real standalone projects from explicit, bounded setup choices."""

from datetime import UTC, date, datetime, timedelta
import math
from typing import Annotated, Literal
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from .domain import COLLECTION_LIMITS, MAX_ASSIGNMENTS, MAX_CANDIDATE_PAIRS, MAX_PLANNING_DAYS, MAX_RECORDS
from .models import Approval, Demand, Employee, Interval, Objectives, Position, RuleProfile, Shift, Snapshot
from .timeutils import localize, minute


Name = Annotated[str, Field(min_length=1, max_length=120)]
Hours = Annotated[float, Field(strict=True, ge=0, le=8784, allow_inf_nan=False)]
Count = Annotated[int, Field(strict=True, ge=0, le=1000)]


class SetupModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class ProjectPerson(SetupModel):
    name: Name
    weekly_hours: Hours | None = None
    target_hours: Hours | None = None
    employment_fraction: Annotated[int, Field(strict=True, ge=1, le=100)] = 100

    @model_validator(mode='after')
    def hours_source(self):
        if (self.weekly_hours is None) == (self.target_hours is None):
            raise ValueError('Pro Person entweder Wochenstunden oder Zielstunden angeben.')
        if self.weekly_hours is not None and self.weekly_hours > 168:
            raise ValueError('Wochenstunden dürfen 168 nicht überschreiten.')
        return self


class ProjectPosition(SetupModel):
    name: Name


class TemplateDemand(SetupModel):
    position: Annotated[int, Field(strict=True, ge=0, le=99)]
    minimum: Count
    maximum: Count

    @model_validator(mode='after')
    def valid_bounds(self):
        if self.maximum < self.minimum:
            raise ValueError('Die Höchstbesetzung muss mindestens der Mindestbesetzung entsprechen.')
        return self


class ShiftTemplate(SetupModel):
    name: Name
    kind: Literal['day', 'night']
    start_time: Annotated[str, Field(pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')]
    end_time: Annotated[str, Field(pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')]
    weekdays: Annotated[list[Annotated[int, Field(strict=True, ge=0, le=6)]], Field(min_length=1, max_length=7)]
    demands: Annotated[list[TemplateDemand], Field(min_length=1, max_length=100)]

    @model_validator(mode='after')
    def unique_days_and_positions(self):
        if self.start_time == self.end_time:
            raise ValueError('Schichtbeginn und Schichtende müssen verschieden sein; 24-Stunden-Schichten aufteilen.')
        if len(set(self.weekdays)) != len(self.weekdays):
            raise ValueError('Wochentage dürfen nicht mehrfach vorkommen.')
        if len({d.position for d in self.demands}) != len(self.demands):
            raise ValueError('Eine Funktion darf pro Schichtvorlage nur einmal vorkommen.')
        if not any(d.maximum for d in self.demands):
            raise ValueError('Mindestens eine Funktion benötigt eine Höchstbesetzung über null.')
        return self


class ProjectRules(SetupModel):
    min_rest_hours: Annotated[float, Field(strict=True, ge=0, le=168, allow_inf_nan=False)]
    after_night_rest_hours: Annotated[float, Field(strict=True, ge=0, le=168, allow_inf_nan=False)] = 0
    max_consecutive_work_days: Annotated[int, Field(strict=True, ge=1, le=31)]
    max_consecutive_nights: Annotated[int, Field(strict=True, ge=1, le=31)]
    max_daily_hours: Annotated[float, Field(strict=True, gt=0, le=25, allow_inf_nan=False)]
    max_weekly_hours: Annotated[float, Field(strict=True, gt=0, le=175, allow_inf_nan=False)]
    weekly_rest_hours: Annotated[float, Field(strict=True, ge=0, le=168, allow_inf_nan=False)] = 36


class ProjectCreateRequest(SetupModel):
    project_name: Name
    period_start: date
    period_end: date
    timezone: Annotated[str, Field(min_length=1, max_length=100)]
    people: Annotated[list[ProjectPerson], Field(min_length=1, max_length=1000)]
    positions: Annotated[list[ProjectPosition], Field(min_length=1, max_length=100)]
    shift_templates: Annotated[list[ShiftTemplate], Field(min_length=1, max_length=32)]
    rules: ProjectRules
    rules_confirmed: StrictBool
    approvals_confirmed: StrictBool = False
    context_duty_free_confirmed: StrictBool = False

    @field_validator('period_start', 'period_end', mode='before')
    @classmethod
    def calendar_dates(cls, value):
        if isinstance(value, datetime) or not isinstance(value, (date, str)):
            raise ValueError('Datum als JJJJ-MM-TT angeben.')
        if isinstance(value, str):
            try:
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError
            except ValueError as exc:
                raise ValueError('Datum als JJJJ-MM-TT angeben.') from exc
        return value

    @field_validator('timezone')
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError('Unbekannte Zeitzone. Beispielsweise Europe/Vienna verwenden.') from exc
        return value

    @model_validator(mode='after')
    def valid_setup(self):
        if not self.rules_confirmed:
            raise ValueError('Die gewählten Planungsregeln müssen ausdrücklich bestätigt werden.')
        days = (self.period_end - self.period_start).days + 1
        if not 1 <= days <= MAX_PLANNING_DAYS:
            raise ValueError('Der Planungszeitraum muss 1 bis 366 Tage umfassen.')
        for label, values in [('Personen', self.people), ('Funktionen', self.positions)]:
            if len({v.name.casefold() for v in values}) != len(values):
                raise ValueError(f'{label} benötigen unterscheidbare Namen.')
        for template in self.shift_templates:
            if any(d.position >= len(self.positions) for d in template.demands):
                raise ValueError('Eine Schichtvorlage verweist auf eine unbekannte Funktion.')
        return self


def _rule_minutes(rules: ProjectRules):
    converted = {}
    for field, label in (
        ('min_rest', 'Mindestruhe'), ('after_night_rest', 'Ruhe nach Nachtdienst'),
        ('weekly_rest', 'Wochenruhe'), ('max_daily', 'Tägliche Höchstarbeitszeit'),
        ('max_weekly', 'Wöchentliche Höchstarbeitszeit'),
    ):
        minutes = getattr(rules, field + '_hours') * 60
        rounded = round(minutes)
        # Allow only floating-point representation noise, not sub-minute rules.
        # Rounding minima down or maxima up would silently weaken confirmed rules.
        if not math.isclose(minutes, rounded, rel_tol=0, abs_tol=2 * math.ulp(minutes)):
            raise ValueError(f'{label}: Stundenwert muss ganzen Minuten entsprechen; beispielsweise 11 oder 11.5 Stunden.')
        converted[field + '_minutes'] = rounded
    return converted


def create_project(data: ProjectCreateRequest) -> Snapshot:
    """Expand recurring shifts only after checking their total execution budget."""
    rule_minutes = _rule_minutes(data.rules)
    days = (data.period_end - data.period_start).days + 1
    occurrences = [
        sum((data.period_start.weekday() + offset) % 7 in template.weekdays for offset in range(days))
        for template in data.shift_templates
    ]
    shift_count = sum(occurrences)
    demand_count = sum(n * len(t.demands) for n, t in zip(occurrences, data.shift_templates))
    minimum_count = sum(n * sum(d.minimum for d in t.demands) for n, t in zip(occurrences, data.shift_templates))
    approval_count = len(data.people) * len(data.positions) if data.approvals_confirmed else 0
    record_count = (5 + 6 * len(data.people) + 2 * approval_count
                    + 2 * len(data.positions) + 4 * shift_count + 2 * demand_count)
    if not shift_count:
        raise ValueError('Für die gewählten Wochentage liegt keine Schicht im Planungszeitraum.')
    if (shift_count > COLLECTION_LIMITS['shifts']
            or demand_count > COLLECTION_LIMITS['demands']
            or demand_count * len(data.people) > MAX_CANDIDATE_PAIRS
            or minimum_count > MAX_ASSIGNMENTS
            or record_count > MAX_RECORDS):
        raise ValueError('Dieses Projekt überschreitet die unterstützte Planungsgröße. Zeitraum, Team oder Schichtbedarf reduzieren.')

    rules = data.rules
    horizon = max(8, rules.max_consecutive_work_days, rules.max_consecutive_nights,
                  (max(rule_minutes['min_rest_minutes'], rule_minutes['after_night_rest_minutes']) + 1439) // 1440)
    if ((data.period_start - date.min).days <= horizon
            or (date.max - data.period_end).days <= horizon + 1):
        raise ValueError('Der Zeitraum liegt zu nahe an der Grenze des unterstützten Datumsbereichs.')
    context_start = data.period_start - timedelta(days=horizon)
    context_end = data.period_end + timedelta(days=horizon)
    profile = RuleProfile(
        id='project-rules', valid_from=context_start, valid_until=context_end,
        **rule_minutes,
        max_consecutive_work_days=rules.max_consecutive_work_days,
        max_consecutive_nights=rules.max_consecutive_nights,
        confirmed=True, source='project-setup',
    )
    positions = [Position(id=f'position-{index + 1}', name=p.name,
                          function_id=f'function-{index + 1}', workplace_id='workplace-1',
                          qualifications_required=False)
                 for index, p in enumerate(data.positions)]
    people = [Employee(
        id=f'person-{index + 1}', name=p.name, team_ids=['team-1'],
        employment_start=context_start, employment_end=context_end,
        approvals=[Approval(function_id=position.function_id, workplace_id=position.workplace_id,
                            valid_from=context_start, valid_until=context_end)
                   for position in positions] if data.approvals_confirmed else [],
        profile_ids=[profile.id], employment_fraction=p.employment_fraction,
        target_minutes=round((p.target_hours if p.target_hours is not None else p.weekly_hours * days / 7) * 60),
    ) for index, p in enumerate(data.people)]

    shifts, demands = [], []
    for offset in range(days):
        day = data.period_start + timedelta(days=offset)
        for index, template in enumerate(data.shift_templates):
            if day.weekday() not in template.weekdays:
                continue
            end_day = day + timedelta(days=int(template.end_time < template.start_time))
            try:
                start = localize(day, template.start_time, data.timezone)
                end = localize(end_day, template.end_time, data.timezone)
            except ValueError as exc:
                raise ValueError(f'Schicht „{template.name}“ am {day}: {exc}') from exc
            paid_minutes = minute(end) - minute(start)
            if paid_minutes <= 0:
                raise ValueError(f'Schicht „{template.name}“ am {day} besitzt keine positive Dauer.')
            shift_id = f'shift-{day.isoformat()}-{index + 1}'
            shifts.append(Shift(id=shift_id, name=template.name,
                                kind=template.kind, team_id='team-1',
                                segments=[Interval(start=start, end=end)],
                                paid_minutes=paid_minutes, source='project-setup'))
            demands.extend(Demand(id=f'{shift_id}-position-{d.position + 1}', shift_id=shift_id,
                                  position_id=positions[d.position].id,
                                  minimum=d.minimum, maximum=d.maximum, source='project-setup')
                           for d in template.demands)

    return Snapshot(
        id=str(uuid4()), revision='0', created_at=datetime.now(UTC), timezone=data.timezone,
        period_start=data.period_start, period_end=data.period_end,
        context_start=context_start, context_end=context_end,
        context_complete=data.context_duty_free_confirmed,
        rule_version='project-rules:1', source='json', employees=people, positions=positions,
        shifts=shifts, demands=demands, profiles=[profile],
        objectives=Objectives(workday_transitions=100),
        metadata={
            'project_name': data.project_name,
            'created_with': 'project-setup',
            'group_tree': [{'id': 'team-1', 'name': 'Team'}],
            'workplaces': [{'id': 'workplace-1', 'name': 'Arbeitsplatz'}],
            'setup_approvals_confirmed': data.approvals_confirmed,
            'context_duty_free_confirmed': data.context_duty_free_confirmed,
            'context_confirmation': {'before_start': context_start.isoformat(),
                                     'after_end': context_end.isoformat()},
            'target_hours_basis': 'Individuelle Wochenstunden × Kalendertage ÷ 7; ohne Feiertagsabzug. Direkte Zielstunden bleiben unverändert.',
        },
    )
