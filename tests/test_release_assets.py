"""Release staging is tested entirely with synthetic bytes, not personnel data."""

import hashlib
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "prepare_release_assets.py"


@pytest.fixture
def artifacts(tmp_path):
    root = tmp_path / "artifacts"
    groups = {
        "openschichtplaner5-generator-python": [
            "openschichtplaner5_generator-1.2.3-py3-none-any.whl",
            "openschichtplaner5_generator-1.2.3.tar.gz",
        ],
        "openschichtplaner5-generator-linux-amd64": [
            "openschichtplaner5-generator-linux-amd64.tar.gz",
        ],
    }
    for group, names in groups.items():
        directory = root / group
        directory.mkdir(parents=True)
        lines = []
        for name in names:
            payload = ("synthetic test bytes: " + name).encode()
            (directory / name).write_bytes(payload)
            lines.append(f"{hashlib.sha256(payload).hexdigest()}  {name}\n")
        (directory / "SHA256SUMS").write_text("".join(lines))
    return root


def stage(artifacts, output, tag="v1.2.3"):
    return subprocess.run([sys.executable, str(SCRIPT), "--artifacts", str(artifacts),
                           "--output", str(output), "--tag", tag],
                          capture_output=True, text=True, timeout=10)


def test_verified_release_files_are_copied_byte_for_byte(artifacts, tmp_path):
    output = tmp_path / "release"
    result = stage(artifacts, output)
    assert result.returncode == 0, result.stderr
    assert len(list(output.iterdir())) == 4
    for directory in artifacts.iterdir():
        for source in directory.iterdir():
            if source.name != "SHA256SUMS":
                assert (output / source.name).read_bytes() == source.read_bytes()
    lines = (output / "SHA256SUMS").read_text().splitlines()
    assert len(lines) == 3
    for line in lines:
        digest, name = line.split("  ")
        assert digest == hashlib.sha256((output / name).read_bytes()).hexdigest()


@pytest.mark.parametrize("fault", ["changed", "missing", "extra", "symlink", "duplicate",
                                   "traversal", "missing-sum", "wrong-version", "invalid-tag", "late-corruption"])
def test_unverified_artifacts_never_create_release_output(artifacts, tmp_path, fault):
    directory = artifacts / "openschichtplaner5-generator-python"
    wheel = directory / "openschichtplaner5_generator-1.2.3-py3-none-any.whl"
    manifest = directory / "SHA256SUMS"
    tag = "v1.2.3"
    if fault == "changed":
        wheel.write_bytes(b"different synthetic bytes")
    elif fault == "missing":
        wheel.unlink()
    elif fault == "extra":
        (directory / "not-a-release-file.json").write_text("synthetic")
    elif fault == "symlink":
        moved = tmp_path / "moved-wheel"
        wheel.rename(moved)
        wheel.symlink_to(moved)
    elif fault == "duplicate":
        manifest.write_text(manifest.read_text() * 2)
    elif fault == "traversal":
        manifest.write_text(manifest.read_text().replace(wheel.name, "../" + wheel.name))
    elif fault == "missing-sum":
        manifest.write_text(manifest.read_text().splitlines()[0] + "\n")
    elif fault == "late-corruption":
        archive = artifacts / "openschichtplaner5-generator-linux-amd64" / "openschichtplaner5-generator-linux-amd64.tar.gz"
        archive.write_bytes(b"changed synthetic Docker archive")
    elif fault == "wrong-version":
        tag = "v1.2.4"
    else:
        tag = "v1.2.3/../../other"
    output = tmp_path / "release"
    assert stage(artifacts, output, tag).returncode != 0
    assert not output.exists()


def test_existing_release_staging_is_not_overwritten(artifacts, tmp_path):
    output = tmp_path / "release"
    output.mkdir()
    previous = output / "SHA256SUMS"
    previous.write_text("previous synthetic manifest")
    assert stage(artifacts, output).returncode != 0
    assert list(output.iterdir()) == [previous]
    assert previous.read_text() == "previous synthetic manifest"
