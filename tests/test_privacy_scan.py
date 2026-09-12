"""Check the pre-publication scanner on synthetic content only."""

import importlib.util
import subprocess
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "privacy_scan.py"
spec = importlib.util.spec_from_file_location("privacy_scan", TOOL)
privacy_scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(privacy_scan)


def run(*args):
    return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True)


def test_reports_planted_findings_without_echoing_them(tmp_path):
    secret = "Sup3rSecretValue123"
    (tmp_path / "leak.py").write_text(f'api_key = "{secret}"\nhost = "10.0.0.1"\n')
    (tmp_path / "roster.csv").write_text("day;service\n")
    names = tmp_path / "names.txt"
    names.write_text("Erika Mustermann\n")
    (tmp_path / "note.md").write_text("Erika Mustermann arbeitet Nachtdienst.\n")

    result = run("--paths", str(tmp_path), "--names", str(names))

    assert result.returncode == 1
    assert "credential" in result.stdout and "private_host" in result.stdout
    assert "blocked_suffix" in result.stdout and "private_name_list" in result.stdout
    assert secret not in result.stdout
    assert "Erika" not in result.stdout


def test_accepts_clean_content(tmp_path):
    (tmp_path / "clean.py").write_text('url = "http://127.0.0.1:8000"\nmail = "team@example.com"\n')

    result = run("--paths", str(tmp_path))

    assert result.returncode == 0
    assert "0 files with hits" in result.stdout


def test_directory_walk_skips_git_ignored_files(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("ignored/\n")
    (tmp_path / "ignored").mkdir()
    (tmp_path / "ignored" / "dump.csv").write_text("x\n")

    collected = list(privacy_scan.collect([tmp_path]))

    assert not any(path.name == "dump.csv" for path in collected)
