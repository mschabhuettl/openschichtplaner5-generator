"""Exercise native search and clean process exit beyond tiny unit models."""

from datetime import date, timedelta
from pathlib import Path
import subprocess
import sys

import pytest

from sp5generator.models import Objectives
from sp5generator.solver import solve
from test_core_rules import case, shift


@pytest.mark.parametrize("native_quality", [False, True])
@pytest.mark.parametrize("attempt", range(3))
def test_fourteen_day_demo_quality_search_survives_fresh_process(attempt, native_quality):
    # This full demo intermittently segfaulted in native parallel CP-SAT
    # quality search. A subprocess makes that failure an ordinary test failure.
    script = """
from sp5generator.demo import make_demo
from sp5generator.solver import solve

result = solve(make_demo(employees=12, days=14), time_limit=15)
assert result.solver_status in {"FEASIBLE", "OPTIMAL"}, result.model_dump_json()
assert result.validation.complete
assert result.metrics["objective_phase"] == "quality"
assert result.parameters["workers"] == 1
assert result.model_dump_json()
"""
    if native_quality:
        # Non-partial demo search has only the quality objective. Keep the
        # candidate policy local to this fresh process; production is unchanged.
        script = """
from ortools.sat.python import cp_model
original = cp_model.CpSolver.solve
calls = []
def native_search(self, model, *args, **kwargs):
    assert self.parameters.num_search_workers == 1
    self.parameters.interleave_search = True
    self.parameters.use_lns_only = True
    self.parameters.cp_model_presolve = True
    calls.append(True)
    return original(self, model, *args, **kwargs)
cp_model.CpSolver.solve = native_search
""" + script + "\nassert calls\n"
    process = subprocess.run(
        [sys.executable, "-X", "faulthandler", "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert process.returncode == 0, (
        f"Native solver attempt {attempt} exited with {process.returncode}:\n"
        + process.stdout
        + process.stderr
    )


def test_weekend_fairness_balances_weeks_despite_different_duty_approvals():
    s = case(2, [shift(f"{day}-{hour}", day, hour, 1)
                 for day in (10, 17) for hour in range(8, 13)])
    s.period_end = date(2026, 1, 18)
    s.profiles[0].min_rest_minutes = 0
    s.positions.append(s.positions[0].model_copy(update={"id": "p2", "function_id": "f2"}))
    s.employees[0].approvals.append(
        s.employees[0].approvals[0].model_copy(update={"function_id": "f2"})
    )
    for demand in s.demands:
        if not demand.id.endswith("-8"):
            demand.position_id = "p2"
    s.objectives = Objectives(hours=0, nights=0, weekends=1, holidays=0,
                              wishes=0, changes=0)
    # Beide können an zwei Wochenenden arbeiten, e0 in zehn Diensten, e1 in zwei.
    result = solve(s, 2)
    assert result.solver_status == "OPTIMAL"
    assert result.validation.valid and result.validation.complete
    duty_dates = {duty.id: duty.segments[0].start.date() for duty in s.shifts}
    worked_weekends = {
        e.id: {duty_dates[a.demand_id] - timedelta(days=duty_dates[a.demand_id].weekday())
               for a in result.assignments if a.employee_id == e.id}
        for e in s.employees
    }
    assert {eid: len(weeks) for eid, weeks in worked_weekends.items()} == {"e0": 2, "e1": 2}


def test_night_fairness_keeps_balanced_assignment_distribution():
    s = case(2, [shift(f"n{day}", day, 20, 2, "night") for day in (5, 6, 7, 8)])
    s.objectives = Objectives(hours=0, nights=1, weekends=0, holidays=0,
                              wishes=0, changes=0)
    result = solve(s, 2)
    assert result.solver_status == "OPTIMAL"
    assert result.validation.valid and result.validation.complete
    assert {
        e.id: sum(a.employee_id == e.id for a in result.assignments) for e in s.employees
    } == {"e0": 2, "e1": 2}
