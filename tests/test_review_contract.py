"""Keep release-facing examples and generated contracts in sync."""
import json
from pathlib import Path
import re
import tomllib

import pytest

from sp5generator import __version__
from sp5generator.cli import main
from sp5generator.demo import make_demo
from sp5generator.models import Result, Snapshot

ROOT = Path(__file__).resolve().parents[1]


def test_readme_promotes_the_package_version():
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    readme = (ROOT / "README.md").read_text()
    assert __version__ == version
    promoted = re.search(r"\*\*Version ([0-9.]+)\*\*", readme)
    assert promoted is not None
    assert promoted.group(1) == version
    assert f"openschichtplaner5_generator-{version}-py3-none-any.whl[web,sp5]" in readme
    assert f"[Release {version} und Aktualisierung](docs/release-{version}.md)" in readme
    assert (ROOT / "docs" / f"release-{version}.md").is_file()


@pytest.mark.parametrize("kind,model", [("input", Snapshot), ("result", Result)])
def test_checked_in_schema_matches_runtime_and_cli(kind, model, capsys):
    checked_in = json.loads((ROOT / "docs" / f"{kind}.schema.json").read_text())
    assert checked_in == model.model_json_schema()
    assert main(["schema", kind]) == 0
    assert json.loads(capsys.readouterr().out) == checked_in


def test_schema_1_0_preserves_optional_field_defaults():
    # Old 1.0 documents can omit subsequently introduced optional settings.
    current = make_demo(4, 2).model_dump(mode="json")
    assert Snapshot.model_validate(current).schema_version == "1.0"
    for person in current["employees"]:
        person.pop("excluded", None)
        person.pop("max_period_minutes", None)
    for demand in current["demands"]:
        demand.pop("alternative_group", None)
    for field in ("isolated_days", "split_weekends", "block_shape", "hours_fairness", "duty_fairness"):
        current["objectives"].pop(field, None)
    restored = Snapshot.model_validate(current)
    assert all(not person.excluded and person.max_period_minutes is None for person in restored.employees)
    assert all(demand.alternative_group is None for demand in restored.demands)
    assert restored.objectives.hours_fairness == 0
