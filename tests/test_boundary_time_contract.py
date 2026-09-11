"""Safety requirements for replacing artificial boundary staffing demands.

These metamorphic checks deliberately demonstrate that an absence is NOT an
equivalent representation of work. All fixtures are synthetic and explicitly
approved; they do not clear import diagnostics or authorize historical duties.
"""

from datetime import date

import pytest

from sp5generator.models import Assignment
from sp5generator.solver import solve
from sp5generator.validator import validate
from test_core_rules import case, shift
from test_spill_rest import spill_case


def boundary_case(rule):
    if rule == "weekly_rest":
        return spill_case()
    if rule in ("consecutive_work", "consecutive_nights"):
        kind = "night" if rule == "consecutive_nights" else "day"
        duties = [shift("before1", 5, 8, 8, kind), shift("before2", 6, 8, 8, kind),
                  shift("new", 7, 8, 8, kind)]
        day = 7
    elif rule == "weekly_limit":
        duties = [shift("before", 5, 8, 8), shift("new", 7, 8, 8)]
        day = 7
    elif rule == "daily_limit":
        duties = [shift("before", 4, 23, 9), shift("new", 5, 12, 8)]
        day = 5
    elif rule == "period_limit":
        duties = [shift("before", 4, 23, 9), shift("new", 5, 12, 8)]
        day = 5
    elif rule == "interleaving":
        before = shift("before", 4, 20, 4)
        before.segments.extend(shift("second-part", 5, 12, 4).segments)
        duties = [before, shift("new", 5, 8, 2)]
        day = 5
    elif rule == "night_rest":
        duties = [shift("before", 4, 20, 8, "night"), shift("new", 5, 16, 8)]
        day = 5
    elif rule == "overlap":
        duties = [shift("before", 4, 23, 12), shift("new", 5, 8, 8)]
        day = 5
    else:
        assert rule == "rest"
        duties = [shift("before", 4, 20, 8), shift("new", 5, 8, 8)]
        day = 5
    snapshot = case(1, duties)
    snapshot.period_start = snapshot.period_end = date(2026, 1, day)
    profile = snapshot.profiles[0]
    profile.min_rest_minutes = 0 if rule in ("daily_limit", "period_limit", "interleaving") else 660
    if rule == "daily_limit":
        profile.max_daily_minutes = 12 * 60
    elif rule == "weekly_limit":
        profile.max_weekly_minutes = 12 * 60
    elif rule == "period_limit":
        profile.max_period_minutes = 12 * 60
    elif rule == "night_rest":
        profile.after_night_rest_minutes = 16 * 60
    elif rule == "consecutive_work":
        profile.max_consecutive_work_days = 2
    elif rule == "consecutive_nights":
        profile.max_consecutive_nights = 2
    snapshot.assignments = [Assignment(employee_id="e0", demand_id=s.id, fixed=True)
                            for s in duties[:-1]]
    return snapshot


def replace_work_by_absence(snapshot):
    """Intentionally lossy TEST-ONLY counterfactual; never use as migration."""
    converted = snapshot.model_copy(deep=True)
    fixed_ids = {a.demand_id for a in converted.assignments}
    shift_ids = {d.shift_id for d in converted.demands if d.id in fixed_ids}
    converted.employees[0].unavailable.extend(
        interval for s in converted.shifts if s.id in shift_ids for interval in s.segments
    )
    converted.shifts = [s for s in converted.shifts if s.id not in shift_ids]
    converted.demands = [d for d in converted.demands if d.id not in fixed_ids]
    converted.assignments = []
    return converted


@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("rule", [
    "rest", "daily_limit", "weekly_limit", "consecutive_work", "consecutive_nights",
    "weekly_rest", "period_limit", "interleaving", "night_rest",
])
def test_absence_substitution_loses_required_boundary_work_constraints(rule, partial):
    snapshot = boundary_case(rule)
    fixed_ids = {a.demand_id for a in snapshot.assignments}
    new_id, = {d.id for d in snapshot.demands} - fixed_ids
    proposed = [*snapshot.assignments, Assignment(employee_id="e0", demand_id=new_id)]
    checked = validate(snapshot, proposed)
    assert not checked.valid
    assert {d.code for d in checked.diagnostics} == {"rest" if rule == "night_rest" else rule}
    # Fixed history alone is valid, so this is a conflict with new work, not
    # rejection of an unrelated historical breach.
    assert validate(snapshot, snapshot.assignments).valid
    result = solve(snapshot, 5, partial=partial)
    if partial:
        assert result.solver_status == "OPTIMAL"
        assert {a.demand_id for a in result.assignments} == fixed_ids
        assert result.vacancies == {new_id: 1}
        assert result.validation.valid and not result.validation.complete
    else:
        assert result.solver_status == "INFEASIBLE"

    lossy = replace_work_by_absence(snapshot)
    checked_lossy = validate(lossy, [Assignment(employee_id="e0", demand_id=new_id)])
    assert checked_lossy.complete
    result_lossy = solve(lossy, 5, partial=partial)
    assert result_lossy.solver_status == "OPTIMAL"
    assert {a.demand_id for a in result_lossy.assignments} == {new_id}
    assert result_lossy.validation.complete


@pytest.mark.parametrize("partial", [False, True])
def test_absence_substitution_only_preserves_direct_overlap_rejection(partial):
    snapshot = boundary_case("overlap")
    proposed = [*snapshot.assignments, Assignment(employee_id="e0", demand_id="new")]
    assert "overlap" in {d.code for d in validate(snapshot, proposed).diagnostics}
    lossy = replace_work_by_absence(snapshot)
    assert "absence" in {d.code for d in validate(lossy, proposed[-1:]).diagnostics}
    for source in (snapshot, lossy):
        result = solve(source, 5, partial=partial)
        assert all(a.demand_id != "new" for a in result.assignments)
        assert result.solver_status == ("OPTIMAL" if partial else "INFEASIBLE")


@pytest.mark.parametrize("partial", [False, True])
def test_boundary_work_counts_elapsed_minutes_but_not_period_paid_target(partial):
    snapshot = boundary_case("weekly_limit")
    snapshot.profiles[0].max_weekly_minutes = 16 * 60  # exact 8h + 8h, accepted
    snapshot.shifts[0].paid_minutes = 6000
    snapshot.shifts[1].paid_minutes = 60
    snapshot.employees[0].target_minutes = 60
    result = solve(snapshot, 5, partial=partial)
    assert result.validation.complete
    assert len(result.assignments) == 2
    metrics = result.metrics["employees"]["e0"]
    assert metrics["paid_minutes"] == 60
    assert metrics["deviation_minutes"] == 0
    snapshot.profiles[0].max_weekly_minutes = 16 * 60 - 1
    assert "weekly_limit" in {d.code for d in validate(snapshot, result.assignments).diagnostics}
