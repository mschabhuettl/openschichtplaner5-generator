"""Synthetic API helper audit; no server import, DBF access or HTTP requests.

Extract the three real helper functions unchanged, excluding router startup.
--candidate asserts an explicitly Ist-only experimental correction, not an
approved endpoint default or a complete independent working-time validator.
"""

import argparse
import ast
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from sp5lib import calculations as calc


def load_helpers(path):
    names = {"_employee_plan", "_collect_day_data", "_check_employee"}
    tree = ast.parse(path.read_text())
    nodes = [node for node in tree.body
             if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in nodes} == names
    namespace = {"date": date, "datetime": datetime, "timedelta": timedelta,
                 "calc": calc}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return SimpleNamespace(**namespace)


def verify(helpers, candidate):
    day = date(2026, 9, 7)
    assertions = 0
    cases = 0
    for kinds, cycle in [((0,), False), ((1,), False), ((0, 1), False),
                         ((), True), ((1,), True), ((0, 1), True)]:
        for special in (None, "replacement", "additive"):
            tables = {
                "MASHI": [{"EMPLOYEEID": 10, "DATE": str(day), "SHIFTID": 5,
                           "TYPE": kind} for kind in kinds],
                "SHIFT": [{"ID": 5, **{f"DURATION{i}": 8 for i in range(8)},
                           **{f"STARTEND{i}": "08:00-16:00" for i in range(8)}}],
                "CYCLE": [{"ID": 1, "SIZE": 1, "UNIT": 0}],
                "CYENT": [{"CYCLEEID": 1, "INDEX": 0, "SHIFTID": 5}],
                "CYASS": [{"EMPLOYEEID": 10, "CYCLEID": 1, "START": str(day),
                           "END": str(day), "ENTRANCE": 0}] if cycle else [],
                "SPSHI": [{"EMPLOYEEID": 10, "DATE": str(day), "TYPE": 1,
                           "SHIFTID": 5 if special == "replacement" else 0,
                           "DURATION": 2, "STARTEND": "18:00-20:00"}]
                if special else [],
            }
            db = SimpleNamespace(_read=lambda table: tables.get(table, []))
            if candidate:
                normal_count = int(0 in kinds or cycle)
            else:
                normal_count = len(kinds) or int(cycle)
            expected_blocks = (0 if special == "replacement" else normal_count)
            expected_hours = expected_blocks * 8
            if special:
                expected_blocks += 1
                expected_hours += 2
            hours, blocks = helpers._collect_day_data(db, 10, day, day)
            assert sum(hours.values()) == expected_hours, (kinds, cycle, special, hours)
            assert len(blocks) == expected_blocks
            # Low synthetic limits expose false positives from alternative plans;
            # they are not user defaults or proposed production configuration.
            rules = {"max_hours_per_day": 10, "max_hours_per_week": 12,
                     "min_rest_hours_between_shifts": 11, "max_consecutive_days": 6}
            violations = helpers._check_employee(db, 10, day, day, rules)
            for kind, limit in (("max_hours_per_day", 10), ("max_hours_per_week", 12)):
                values = [v["value"] for v in violations if v["type"] == kind]
                assert values == ([expected_hours] if expected_hours > limit else [])
            assertions += 4
            cases += 1
    return {"synthetic_only": True, "candidate": candidate,
            "cases": cases, "assertions": assertions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("router", type=Path)
    parser.add_argument("--candidate", action="store_true")
    parser.add_argument("--helper-tests", type=Path,
                        help="Also run upstream pure helper tests, excluding config and HTTP tests")
    args = parser.parse_args()
    helpers = load_helpers(args.router)
    result = verify(helpers, args.candidate)
    if args.helper_tests:
        router = ast.parse(args.router.read_text())
        defaults = next(node for node in router.body
                        if isinstance(node, ast.AnnAssign)
                        and isinstance(node.target, ast.Name)
                        and node.target.id == "_DEFAULT_RULES")
        helpers._DEFAULT_RULES = ast.literal_eval(defaults.value)
        tree = ast.parse(args.helper_tests.read_text())
        excluded = {"test_load_rules_corrupt_file_returns_defaults",
                    "test_check_all_skips_employee_without_id"}
        nodes = [node for node in tree.body
                 if isinstance(node, (ast.FunctionDef, ast.ClassDef))
                 and node.name not in excluded]
        namespace = {"wtr": helpers, "date": date, "datetime": datetime,
                     "_RULES": dict(helpers._DEFAULT_RULES)}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(args.helper_tests), "exec"),
             namespace)
        count = 0
        for name, test in namespace.items():
            if name.startswith("test_"):
                test()
                count += 1
        result["upstream_pure_helper_tests"] = count
    print(json.dumps(result))


if __name__ == "__main__":
    main()
