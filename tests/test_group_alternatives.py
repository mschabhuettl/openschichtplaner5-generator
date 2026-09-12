"""Several groups stating the same duty state alternatives, not a sum."""
from datetime import date

import pytest

from sp5generator.domain import eligibility

pytest.importorskip("sp5lib")
from sp5generator.sp5_adapter import import_snapshot  # noqa: E402
from test_sp5_adapter import SyntheticDatabase  # noqa: E402


def source(rows):
    class Source(SyntheticDatabase):
        def get_groups(self):
            return [{"ID": gid} for gid in sorted({r["group_id"] for r in rows})]

        def get_employee_groups(self, employee):
            return sorted({r["group_id"] for r in rows})

        def get_staffing_requirements(self):
            base = super().get_staffing_requirements()["shift_requirements"][0]
            return {"shift_requirements": [{**base, **row} for row in rows]}

    return Source()


def imported(rows, team_ids):
    return import_snapshot(source(rows), date(2026, 1, 6), date(2026, 1, 6),
                           timezone="UTC", team_ids=team_ids)


def test_highest_group_requirement_counts_instead_of_the_sum():
    snapshot = imported([{"id": 401, "group_id": 1, "min": 1, "max": 1},
                         {"id": 402, "group_id": 2, "min": 3, "max": 4}], ["1", "2"])

    demand, = snapshot.demands
    assert (demand.minimum, demand.maximum) == (3, 4)
    assert demand.team_ids == ["sp5:group:1", "sp5:group:2"]
    assert snapshot.metadata["merged_group_requirements"] == 1
    assert any("höchste Teamanforderung" in note for note in snapshot.unresolved)


def test_every_stating_group_may_staff_the_merged_duty():
    snapshot = imported([{"id": 401, "group_id": 1, "min": 1, "max": 1},
                         {"id": 402, "group_id": 2, "min": 1, "max": 1}], ["1", "2"])
    demand, = snapshot.demands
    employee = snapshot.employees[0]

    for team in ("sp5:group:1", "sp5:group:2"):
        employee.team_ids = [team]
        assert "team" not in eligibility(snapshot, employee, demand)
    employee.team_ids = ["sp5:group:9"]
    assert "team" in eligibility(snapshot, employee, demand)


def test_one_group_stays_exactly_as_stated():
    snapshot = imported([{"id": 401, "group_id": 1, "min": 2, "max": 2}], ["1"])

    demand, = snapshot.demands
    assert (demand.minimum, demand.maximum) == (2, 2)
    assert demand.team_ids == ["sp5:group:1"]
    assert snapshot.metadata["merged_group_requirements"] == 0
    assert not any("höchste Teamanforderung" in note for note in snapshot.unresolved)


def test_rows_inside_one_group_keep_their_own_meaning():
    """An explicit MAX=0 ban must never be absorbed by another row."""
    snapshot = imported([{"id": 401, "group_id": 1, "workplace_id": 0, "min": 1, "max": -1},
                         {"id": 402, "group_id": 1, "workplace_id": 0, "min": 0, "max": 0}], ["1"])

    assert sorted((d.minimum, d.maximum) for d in snapshot.demands) == [(0, 0), (1, None)]
