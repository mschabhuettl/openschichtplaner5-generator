"""Exercise native search and clean process exit beyond tiny unit models."""

from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("native_quality", [False, True])
@pytest.mark.parametrize("attempt", range(3))
def test_fourteen_day_demo_quality_search_survives_fresh_process(attempt, native_quality):
    # This full demo intermittently segfaulted in native parallel CP-SAT
    # quality search. A subprocess makes that failure an ordinary test failure.
    script = """
from sp5generator.demo import make_demo
from sp5generator.solver import solve

result = solve(make_demo(employees=12, days=14), time_limit=5)
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
