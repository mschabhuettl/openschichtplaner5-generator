"""Synthetic weekly-model contract tests; no server, source data or network.

Run against the original router for characterization, then with the isolated
candidate and SP5_WEEK_MODEL_CANDIDATE=1 for the missing-model correction.
"""
import os
from datetime import date
from pathlib import Path

import pytest

from tools.audit_upstream_work_time_plan import load_helpers
from tools.test_upstream_work_time_boundaries import rules, source


def check(employee, *, mode="model", cap=6):
    helpers = load_helpers(Path(os.environ["SP5_WORK_TIME_ROUTER"]))
    db = source([(5, "08:00-16:00", 8)])
    db.get_employee = lambda employee_id: employee
    return helpers._check_employee(
        db, 10, date(2026, 1, 5), date(2026, 1, 11),
        rules(max_hours_per_week=cap, week_limit_mode=mode, week_limit_factor=1),
    )


@pytest.mark.parametrize("employee", [
    {},
    {"CALCBASE": 2, "HRSMONTH": 160, "HRSDAY": 0, "WORKDAYS": "11111000"},
    {"CALCBASE": 3, "HRSTOTAL": 160, "WORKDAYS": "11111000"},
])
def test_unresolved_model_is_not_successful_weekly_check(employee):
    result = check(employee)
    if os.environ.get("SP5_WEEK_MODEL_CANDIDATE") == "1":
        assert len(result) == 1
        assert result[0]["type"] == "weekly_model_unresolved"
        assert result[0]["severity"] == "warning"
        assert result[0]["date"] == "2026-01-05"
        assert result[0]["value"] == 0
        # Neither a fallback six-hour cap nor an eight-hour violation is invented.
        assert not any(v["type"] == "max_hours_per_week" for v in result)
    else:
        assert result == []  # Characterizes the ORIGINAL false all-clear.


def test_model_mode_replaces_not_combines_fixed_cap():
    employee = {"CALCBASE": 1, "HRSWEEK": 40, "WORKDAYS": "11111000"}
    assert check(employee) == []
    fixed = check(employee, mode="fixed")
    assert [(v["type"], v["value"], v["limit"]) for v in fixed] == [
        ("max_hours_per_week", 8, 6),
    ]


def test_month_model_uses_partial_month_daily_nominal_not_week_field():
    employee = {"CALCBASE": 2, "HRSMONTH": 160, "HRSDAY": 1,
                "HRSWEEK": 40, "WORKDAYS": "11111000"}
    result = check(employee)
    assert [(v["type"], v["value"], v["limit"]) for v in result] == [
        ("max_hours_per_week", 8, 5),
    ]


def test_fixed_mode_does_not_require_nominal_model():
    assert check({}, mode="fixed", cap=10) == []
