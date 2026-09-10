"""Reproducible synthetic benchmark; prints only aggregate machine-readable metrics."""

import argparse
import json
import os
import platform
from importlib.metadata import version
from sp5generator.demo import make_demo
from sp5generator.solver import solve

parser = argparse.ArgumentParser()
parser.add_argument("--employees", type=int, default=120)
parser.add_argument("--days", type=int, default=31)
parser.add_argument("--time-limit", type=float, default=30)
args = parser.parse_args()
snapshot = make_demo(args.employees, args.days)
result = solve(snapshot, time_limit=args.time_limit)
print(
    json.dumps(
        {
            "python": platform.python_version(),
            "system": platform.system(),
            "architecture": platform.machine(),
            "logical_cpus": os.cpu_count(),
            "ortools": version("ortools"),
            "employees": len(snapshot.employees),
            "days": args.days,
            "shifts": len(snapshot.shifts),
            "demands": len(snapshot.demands),
            "minimum_assignments": sum(d.minimum for d in snapshot.demands),
            "time_limit": args.time_limit,
            "status": result.solver_status,
            "runtime_seconds": result.runtime_seconds,
            "assignments": len(result.assignments),
            "valid": result.validation.valid,
            "complete": result.validation.complete,
            "objective_value": result.objective_value,
            "best_bound": result.best_bound,
            "parameters": result.parameters,
        },
        indent=2,
    )
)
