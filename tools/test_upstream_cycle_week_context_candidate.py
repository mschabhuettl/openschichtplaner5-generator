"""Exercise the staged Library correction with synthetic data and a write trap."""
import ast
from pathlib import Path
import subprocess

import pytest
from sp5lib import database
from test_upstream_cycle_hours import run_cycle


@pytest.fixture
def candidate(monkeypatch, tmp_path):
    target = tmp_path / 'sp5lib/database.py'
    target.parent.mkdir()
    target.write_text(Path(database.__file__).read_text())
    patch = Path(__file__).with_name('upstream-library-cycle-week-context-candidate.patch')
    subprocess.run(['git', 'apply', '--unsafe-paths', '--directory=' + str(tmp_path),
                    str(patch)], check=True, capture_output=True)
    tree = ast.parse(target.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SP5Database')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                  and n.name == 'generate_schedule_from_cycle')
    namespace = dict(vars(database))
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(target), 'exec'), namespace)
    monkeypatch.setattr(database.SP5Database, method.name, namespace[method.name])


@pytest.mark.parametrize('year,month,start,context,created', [
    (2026, 9, '2026-09-02', '2026-08-31', 0),
    (2026, 9, '2026-09-02', '2026-09-01', 0),
    (2026, 9, '2026-09-02', '2026-08-30', 1),
    (2026, 9, '2026-09-30', '2026-10-01', 0),
    (2026, 9, '2026-09-30', '2026-10-05', 1),
    (2027, 1, '2027-01-01', '2026-12-31', 0),
    (2026, 12, '2026-12-31', '2027-01-01', 0),
])
@pytest.mark.parametrize('force', [False, True])
def test_context_both_month_edges_and_iso_year(candidate, monkeypatch, tmp_path,
                                              year, month, start, context, created, force):
    result = run_cycle(monkeypatch, tmp_path, year=year, month=month, start=start,
                       existing_day=context, force=force)
    assert result['errors'] == []
    assert result['created'] == created
    assert result['skipped_hours_limit'] == 1 - created


@pytest.mark.parametrize('weekly,created', [(0, 1), (15, 0), (16, 1)])
def test_preserves_paid_duration_and_hrsweek_policy(candidate, monkeypatch, tmp_path,
                                                  weekly, created):
    result = run_cycle(monkeypatch, tmp_path, weekly=weekly, existing_day='2026-08-31')
    assert result['errors'] == []
    assert result['created'] == created


@pytest.mark.parametrize('force', [False, True])
def test_existing_same_day_double_count_is_separate_unfixed_issue(candidate, monkeypatch,
                                                                tmp_path, force):
    # The existing branch checks the old duty plus candidate before skip/replace.
    # Keep this defect explicit instead of hiding it behind the boundary fix.
    result = run_cycle(monkeypatch, tmp_path, existing_day='2026-09-02', force=force)
    assert result['created'] == 0
    assert result['skipped_hours_limit'] == 1
    assert result['skipped'] == 0
