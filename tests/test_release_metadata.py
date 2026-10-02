"""Keep current release instructions aligned with the shipped workspace."""
from pathlib import Path
import re
import tomllib

import sp5generator

ROOT = Path(__file__).resolve().parents[1]


def test_current_release_version_and_installation_example_agree():
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    assert sp5generator.__version__ == version
    readme = (ROOT / "README.md").read_text()
    assert f"**Version {version}**" in readme
    assert f"openschichtplaner5_generator-{version}-py3-none-any.whl[web,sp5]" in readme
    assert f"(docs/release-{version}.md)" in readme
    release = (ROOT / f"docs/release-{version}.md").read_text()
    assert release.startswith(f"# Version {version} ")
    for name in ("BASELINE.md", "TARGET-WORKFLOW.md"):
        header = (ROOT / "docs" / "ux" / name).read_text().split("\n\n", 1)[0]
        assert f"(../release-{version}.md)" in header


def test_readme_lists_only_the_four_current_main_workspaces():
    readme = (ROOT / "README.md").read_text()
    section = readme.split("## Arbeitsbereiche\n", 1)[1].split("\n\nGrößere Listen", 1)[0]
    labels = re.findall(r"^- \*\*([^*]+):\*\*", section, re.MULTILINE)
    assert labels == ["Projekte", "Plan", "Team", "Einrichtung"]


def test_standalone_instructions_use_current_setup_routes():
    instructions = (ROOT / "docs/standalone-web.md").read_text()
    assert "**Projekte**, **Plan**, **Team** und **Einrichtung**" in instructions
    assert "**Einrichtung → Regeln & Projektdaten → Dienste**" in instructions
    assert "**Regeln & Bedarf" not in instructions
