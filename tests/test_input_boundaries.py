"""Synthetic regressions for inputs that previously escaped preflight checks."""
from datetime import date, timedelta

import pytest

from sp5generator.demo import make_demo
from sp5generator.domain import input_diagnostics
from sp5generator.solver import solve
from sp5generator.validator import validate


@pytest.mark.parametrize('limit', [float('nan'), float('inf'), float('-inf')])
def test_nonfinite_time_limit_is_rejected_before_planning(limit, monkeypatch):
    def unexpected_validation(snapshot):
        pytest.fail('Invalid time limit reached planning input validation')
    monkeypatch.setattr('sp5generator.solver.input_diagnostics', unexpected_validation)
    with pytest.raises(ValueError, match='Zeitlimit.*endliche'):
        solve(make_demo(), time_limit=limit)


@pytest.mark.parametrize('limit', ['nan', 'inf', '-inf'])
def test_cli_nonfinite_time_limit_reports_input_error_without_result(tmp_path, capsys, limit, monkeypatch):
    import json
    from sp5generator.cli import main
    def unexpected_validation(snapshot):
        pytest.fail('Invalid CLI time limit reached planning input validation')
    monkeypatch.setattr('sp5generator.solver.input_diagnostics', unexpected_validation)
    source = tmp_path / 'synthetic.json'
    output = tmp_path / 'result.json'
    source.write_text(make_demo().model_dump_json())
    assert main(['solve', str(source), '--time-limit=' + limit, '-o', str(output)]) == 2
    assert not output.exists()
    captured = capsys.readouterr()
    assert not captured.out
    assert 'endliche' in json.loads(captured.err)['message']


@pytest.mark.parametrize("case", ["seconds", "microseconds", "offset", "integer", "date", "horizon"])
def test_invalid_boundaries_return_diagnostics_instead_of_crashing(case):
    snapshot = make_demo()
    if case in ("seconds", "microseconds", "offset"):
        snapshot.employees[0].availability[0].start_time = {
            "seconds": "08:00:01", "microseconds": "08:00:00.000001",
            "offset": "08:00+03:00",
        }[case]
    elif case == "integer":
        snapshot.demands[0].maximum = 10**30
    elif case == "date":
        snapshot.context_end = date.max
    else:
        snapshot.profiles[0].max_consecutive_work_days = 2**31 - 1
    assert input_diagnostics(snapshot)
    checked = validate(snapshot, snapshot.assignments)
    assert not checked.valid and checked.diagnostics
    result = solve(snapshot, time_limit=0.1)
    assert result.solver_status == "MODEL_INVALID"
    assert result.validation.diagnostics


def test_ordinary_synthetic_input_still_passes_preflight():
    assert input_diagnostics(make_demo()) == []


@pytest.mark.parametrize("case", ["period", "context", "collection", "nested", "candidates", "local_windows"])
def test_work_budgets_fail_before_expensive_validation(case):
    snapshot = make_demo()
    if case == "period":
        snapshot.period_end = snapshot.period_start + timedelta(days=366)
    elif case == "context":
        snapshot.context_end = snapshot.context_start + timedelta(days=1096)
    elif case == "collection":
        snapshot.assignments *= 5001
    elif case == "nested":
        snapshot.employees[0].availability *= 26000
    elif case == "candidates":
        snapshot.employees = [snapshot.employees[0]] * 500
        snapshot.demands = [snapshot.demands[0]] * 5000
    else:
        snapshot.employees = [snapshot.employees[0]] * 1000
        snapshot.profiles[0].weekly_rest_frame = "rolling_local"
    result = solve(snapshot, time_limit=0.1)
    assert result.solver_status == "MODEL_INVALID"
    assert result.validation.diagnostics[0].code == "size_limit"


def test_external_assignment_budget():
    snapshot = make_demo()
    result = validate(snapshot, snapshot.assignments * 5001)
    assert not result.valid
    assert result.diagnostics[0].code == "size_limit"


def test_120_person_31_day_benchmark_fits_preflight_budgets():
    assert input_diagnostics(make_demo(employees=120, days=31)) == []


def test_staffing_slot_budget_prevents_unbounded_candidate_expansion():
    snapshot = make_demo()
    snapshot.demands[0].minimum = snapshot.demands[0].maximum = 2**31 - 1
    result = solve(snapshot, time_limit=0.1)
    assert result.solver_status == "MODEL_INVALID"
    assert result.validation.diagnostics[0].code == "size_limit"


def test_nested_record_count_does_not_double_count_list_records():
    from sp5generator.domain import planning_record_count
    assert planning_record_count({"rows": [{"id": 1}, {"id": 2}]}) == 3
    assert planning_record_count({"rows": [{"parts": [{"start": 1, "end": 2}]}]}) == 3
    assert planning_record_count({"ids": [1, 2, 3]}) == 4
