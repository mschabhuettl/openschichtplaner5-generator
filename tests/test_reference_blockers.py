"""Synthetic distinction between comparison metadata and mandatory assignments."""

from datetime import date

import pytest

pytest.importorskip("sp5lib")
from sp5generator.models import Approval
from sp5generator.solver import solve
from sp5generator.sp5_adapter import import_snapshot
from sp5generator.validator import validate
from test_sp5_adapter import ExistingPlanDatabase


class ComparisonSource(ExistingPlanDatabase):
    def get_shifts(self, **kwargs):
        row = super().get_shifts(**kwargs)[0]
        return [row, {**row, "ID": 202, "NAME": "Synthetic comparison-only duty"}]

    def get_schedule(self, year, month, **kwargs):
        return [{**row, "shift_id": 202}
                for row in super().get_schedule(year, month, **kwargs)]

    def get_restrictions(self):
        return []


def configured_fixture(mode, plan):
    snapshot = import_snapshot(ComparisonSource(), date(2026, 1, 6), date(2026, 1, 6),
                               "1", "UTC", existing_plan_mode=mode, reference_plan=plan)
    # Test-only complete setup for freshly constructed records, never a helper
    # for clearing real import prerequisites. Keep the reference issue intact.
    snapshot.unresolved = [text for text in snapshot.unresolved
                           if "keine eindeutige Zuordnung" in text]
    snapshot.context_complete = True
    for profile in snapshot.profiles:
        profile.confirmed = True
    for shift in snapshot.shifts:
        shift.kind = "day"
    for employee in snapshot.employees:
        employee.approvals = [Approval(function_id="sp5:service:201", workplace_id="*",
                                       valid_from=date(2026, 1, 1),
                                       valid_until=date(2026, 12, 31))]
    return snapshot


@pytest.mark.parametrize("plan", ["ist", "soll"])
@pytest.mark.parametrize("mode", ["reference", "fixed"])
def test_unmapped_comparison_does_not_become_a_mandatory_assignment(mode, plan):
    snapshot = configured_fixture(mode, plan)
    reference = snapshot.metadata["reference_schedule"][0]
    assert reference["resolution_reason"] == "missing_demand"
    assert reference["planning_blocker"] is (mode == "fixed")
    assert reference["candidate_demand_ids"] == []
    assert not snapshot.assignments
    assert len(snapshot.demands) == 1
    result = solve(snapshot, 3)
    if mode == "fixed":
        assert result.solver_status == "MODEL_INVALID"
        assert not result.assignments
        assert any("keine eindeutige Zuordnung" in d.message
                   for d in result.validation.diagnostics)
    else:
        assert result.solver_status == "OPTIMAL"
        assert len(result.assignments) == 1
        assert validate(snapshot, result.assignments).complete
        assert snapshot.positions[0].function_id == "sp5:service:201"


@pytest.mark.parametrize("missing", ["approval", "profile", "context", "prerequisite"])
def test_optional_reference_does_not_waive_mandatory_setup(missing):
    snapshot = configured_fixture("reference", "ist")
    if missing == "approval":
        snapshot.employees[0].approvals = []
    elif missing == "profile":
        snapshot.profiles[0].confirmed = False
    elif missing == "context":
        snapshot.context_complete = False
    else:
        snapshot.unresolved.append("Synthetic mandatory prerequisite")
    result = solve(snapshot, 3)
    if missing == "context":
        # Existing contract permits a provisional plan, but never complete
        # validation without confirmed boundary context.
        assert not result.validation.complete
        assert any(d.code == "context" for d in result.validation.diagnostics)
        return
    assert result.solver_status == ("INFEASIBLE" if missing == "approval" else "MODEL_INVALID")
    assert not result.assignments
