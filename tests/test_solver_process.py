"""Exercise native search and clean process exit beyond tiny unit models."""

from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("attempt", range(3))
def test_fourteen_day_demo_quality_search_survives_fresh_process(attempt):
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
