"""Correctness boundaries of the prepared checker and grouped duty model."""

from datetime import timedelta
from itertools import product
from pathlib import Path
import subprocess
import sys

import pytest

from sp5generator.demo import make_demo
from sp5generator import domain, solver, validator
from sp5generator.models import Assignment
from sp5generator.solver import solve
from sp5generator.validator import PreparedValidator, validate
from test_core_rules import case, shift


def test_prepared_validator_keeps_input_isolated_and_checks_every_proposal():
    snapshot = case(1, [shift("a", 5, 8, 8), shift("b", 5, 16, 8)])
    prepared = PreparedValidator(snapshot)
    valid_plan = [Assignment(employee_id="e0", demand_id="a")]
    invalid_plan = valid_plan + [Assignment(employee_id="e0", demand_id="b")]
    for plan in ([], valid_plan, invalid_plan, valid_plan * 2, valid_plan):
        assert prepared.validate(plan) == validate(snapshot, plan)
    snapshot.employees[0].approvals.clear()
    assert prepared.validate(valid_plan).valid
    assert not validate(snapshot, valid_plan).valid


@pytest.mark.parametrize("gap", [0, 719, 720])
def test_grouped_position_conflicts_match_independent_checker_exhaustively(gap):
    first = shift("a", 5, 8, 8)
    second = shift("b", 5, 16, 8)
    for interval in second.segments:
        interval.start += timedelta(minutes=gap)
        interval.end += timedelta(minutes=gap)
    snapshot = case(2, [first, second])
    # Different profile sets must keep their own rest limits.
    unrestricted = snapshot.profiles[0].model_copy(update={"id": "unrestricted", "min_rest_minutes": 0})
    snapshot.profiles.append(unrestricted)
    snapshot.employees[1].profile_ids = [unrestricted.id]
    snapshot.demands += [
        d.model_copy(update={"id": d.id + "-second-position"})
        for d in snapshot.demands
    ]
    for chosen in product(range(2), repeat=len(snapshot.demands)):
        plan = [
            Assignment(employee_id=f"e{employee}", demand_id=demand.id, fixed=True)
            for employee, demand in zip(chosen, snapshot.demands)
        ]
        snapshot.assignments = plan
        checked = validate(snapshot, plan)
        result = solve(snapshot, time_limit=1)
        assert result.validation.complete == checked.complete
        assert result.solver_status == ("OPTIMAL" if checked.complete else "INFEASIBLE")


def test_tiny_deadline_stops_before_constructing_a_month_model():
    result = solve(make_demo(120, 31), time_limit=0.000001)
    assert result.solver_status == "UNKNOWN"
    assert any(d.code == "time_limit" for d in result.validation.diagnostics)
    assert "model_variables" not in result.parameters


def test_grouped_conflicts_preserve_split_duty_interleaving():
    split = shift("split", 5, 8, 2)
    split.segments += shift("late-part", 5, 16, 2).segments
    split.paid_minutes = 240
    snapshot = case(1, [split, shift("between", 5, 12, 2)])
    snapshot.profiles[0].min_rest_minutes = 0
    plan = [Assignment(employee_id="e0", demand_id=d.id) for d in snapshot.demands]
    assert any(d.code == "interleaving" for d in validate(snapshot, plan).diagnostics)
    assert solve(snapshot, time_limit=1).solver_status == "INFEASIBLE"


def test_optional_staffing_stays_inside_supported_assignment_limit(monkeypatch):
    # Use the same small cap in all three contract layers to exercise optional
    # staffing without constructing thousands of irrelevant duty variables.
    for module in (domain, solver, validator):
        monkeypatch.setattr(module, "MAX_ASSIGNMENTS", 2)
    snapshot = case(1, [shift("a", 5, 8, 8), shift("b", 6, 8, 8), shift("c", 7, 8, 8)])
    for demand in snapshot.demands:
        demand.minimum = 0
    snapshot.employees[0].target_minutes = 3 * 480
    result = solve(snapshot, time_limit=1)
    assert result.solver_status == "OPTIMAL"
    assert len(result.assignments) == 2
    assert validate(snapshot, result.assignments).complete


@pytest.mark.parametrize("attempt", range(2))
def test_certified_quality_search_survives_fresh_process(attempt):
    script = """
from sp5generator.demo import make_demo
from sp5generator.solver import solve

result = solve(make_demo(40, 14), time_limit=5)
assert result.solver_status in {"FEASIBLE", "OPTIMAL"}, result.model_dump_json()
assert result.validation.complete
assert result.parameters["workers"] == 1
assert result.parameters["quality_presolve"] is False
assert result.parameters["first_feasible_seconds"] < result.runtime_seconds
assert result.parameters["last_optimization_status"] in {"FEASIBLE", "OPTIMAL"}
"""
    process = subprocess.run(
        [sys.executable, "-X", "faulthandler", "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert process.returncode == 0, (
        f"Certified search attempt {attempt} exited with {process.returncode}:\n"
        + process.stdout + process.stderr
    )
