"""Controlled real CP searches exercise tier deadlines and conditional bounds."""

import pytest
from ortools.sat.python import cp_model

from sp5generator import solver
from sp5generator.models import Diagnostic, Validation
from sp5generator.validator import validate
from test_weekend_tier import assert_complete, split_count, weekend_case


@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("enabled", [False, True])
def test_coupling_shares_coverage_budget_and_reserves_quality(monkeypatch, partial, enabled):
    snapshot = weekend_case()
    snapshot.objectives.split_weekends = int(enabled)
    real_search = cp_model.CpSolver.solve
    elapsed = [0.0]

    def exhaust_budget(self, model, *args, **kwargs):
        status = real_search(self, model, *args, **kwargs)
        assert status == cp_model.OPTIMAL
        elapsed[0] += self.parameters.max_time_in_seconds
        return cp_model.FEASIBLE

    monkeypatch.setattr(solver, "monotonic", lambda: elapsed[0])
    monkeypatch.setattr(cp_model.CpSolver, "solve", exhaust_budget)
    result = solver.solve(snapshot, time_limit=100, partial=partial, _repair=False)

    assert_complete(snapshot, result)
    trace = result.parameters["search_trace"]
    first = "vacancies" if partial else "feasibility"
    if enabled:
        assert [entry["phase"] for entry in trace] == [first, "couple", "quality"]
        expected_budgets = [50, 30, 19]
        assert split_count(result.assignments) == 0
        assert result.parameters["split_weekend_count"] == 0
    elif partial:
        assert [entry["phase"] for entry in trace] == [first, "quality"]
        expected_budgets = [80, 19]
    else:
        assert [entry["phase"] for entry in trace] == [first]
        expected_budgets = [100]
    assert [entry["budget_seconds"] for entry in trace] == pytest.approx(expected_budgets)
    assert [entry["search_seconds"] for entry in trace] == pytest.approx(expected_budgets)
    assert result.runtime_seconds == pytest.approx(sum(expected_budgets))


@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("coupling_status", [cp_model.FEASIBLE, cp_model.OPTIMAL])
def test_quality_can_improve_unproven_coupling_but_preserves_proven_value(
    monkeypatch, partial, coupling_status,
):
    snapshot = weekend_case()
    snapshot.objectives.hours = 0
    real_search = cp_model.CpSolver.solve
    searches = []

    def restricted_search(self, model, *args, **kwargs):
        searches.append(model)
        if len(searches) <= 2:
            # Supply a real, valid split incumbent to coverage and coupling.
            # The injected native status isolates how the next phase treats
            # an asserted optimum versus an incumbent without a proof.
            model = model.clone()
            for index, variable in enumerate(model.proto.variables):
                if variable.name.startswith("assign:"):
                    model.add(model.get_int_var_from_proto_index(index) == int(
                        variable.name in {"assign:e0:sat", "assign:e1:sun"}
                    ))
        status = real_search(self, model, *args, **kwargs)
        assert status == cp_model.OPTIMAL
        return coupling_status if len(searches) == 2 else status

    monkeypatch.setattr(cp_model.CpSolver, "solve", restricted_search)
    result = solver.solve(snapshot, time_limit=5, partial=partial)

    assert_complete(snapshot, result)
    coverage, couple, quality = result.parameters["search_trace"]
    assert coverage["vacancy_count"] == couple["vacancy_count"] == quality["vacancy_count"] == 0
    assert couple["phase"] == "couple"
    assert couple["split_weekend_count"] == 2
    assert quality["phase"] == "quality"
    expected = 0 if coupling_status == cp_model.FEASIBLE else 2
    assert split_count(result.assignments) == expected
    assert result.parameters["split_weekend_count"] == expected
    assert result.metrics["objective_contributions"]["split_weekends"] == expected
    assert result.parameters["split_weekends_proven"]
    assert all(left is not right for left, right in zip(searches, searches[1:]))


def test_quality_optimum_does_not_prove_nonzero_coupling_incumbent(monkeypatch):
    snapshot = weekend_case()
    snapshot.profiles[0].max_weekly_minutes = 480
    real_search = cp_model.CpSolver.solve
    searches = []

    def unproven_coupling(self, model, *args, **kwargs):
        searches.append(True)
        status = real_search(self, model, *args, **kwargs)
        assert status == cp_model.OPTIMAL
        return cp_model.FEASIBLE if len(searches) == 2 else status

    monkeypatch.setattr(cp_model.CpSolver, "solve", unproven_coupling)
    result = solver.solve(snapshot, time_limit=5, partial=True)

    assert_complete(snapshot, result)
    assert split_count(result.assignments) == 2
    assert result.parameters["split_weekend_count"] == 2
    assert result.parameters["coverage_proven"]
    assert not result.parameters["split_weekends_proven"]
    assert result.solver_status == "FEASIBLE"
    assert result.metrics["objective_phase"] == "quality"
    assert "coupling unproven" in result.metrics["quality_scope"]
    assert result.parameters["search_trace"][-1]["native_status"] == "OPTIMAL"


def test_rejected_coupling_then_timeout_keeps_validated_coverage_plan(monkeypatch):
    snapshot = weekend_case()
    real_search = cp_model.CpSolver.solve
    real_validate = solver.validate
    searches = []
    coverage_plan = []

    def search(self, model, *args, **kwargs):
        searches.append(True)
        if len(searches) == 3:
            return cp_model.UNKNOWN
        return real_search(self, model, *args, **kwargs)

    def reject_coupling(source, assignments):
        checked = real_validate(source, assignments)
        if len(searches) == 1:
            coverage_plan.extend(assignments)
        if len(searches) == 2:
            assert checked.valid
            # A synthetic independent rejection exercises separation and
            # fallback without weakening the real validator's hard rules.
            return Validation(valid=False, complete=False, diagnostics=[
                Diagnostic(code="night_block", message="Synthetic coupling rejection"),
            ])
        return checked

    monkeypatch.setattr(cp_model.CpSolver, "solve", search)
    monkeypatch.setattr(solver, "validate", reject_coupling)
    result = solver.solve(snapshot, time_limit=5, partial=True)

    assert_complete(snapshot, result)
    assert result.assignments == coverage_plan
    assert validate(snapshot, result.assignments).complete
    assert result.metrics["objective_phase"] == "vacancies"
    assert result.solver_status == "FEASIBLE"
    assert result.parameters["split_weekend_count"] == split_count(coverage_plan)
    coverage, rejected, timeout = result.parameters["search_trace"]
    assert coverage["accepted"]
    assert rejected["phase"] == timeout["phase"] == "couple"
    assert not rejected["independently_valid"] and not rejected["accepted"]
    assert timeout["native_status"] == "UNKNOWN"
