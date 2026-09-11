"""Stage only checksum-verified files from an exact, successful release CI run.

The workflow handles provenance and downloads using GitHub's existing tools.
This helper never builds, uploads, extracts, or executes artifact contents.
"""

import argparse
import hashlib
from pathlib import Path
import re
import shutil


PYTHON_ARTIFACT = "openschichtplaner5-generator-python"
DOCKER_ARTIFACT = "openschichtplaner5-generator-linux-amd64"
DOCKER_ARCHIVE = DOCKER_ARTIFACT + ".tar.gz"


def prepare(artifacts: Path, output: Path, tag: str):
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
        raise ValueError("Expected a release tag of the form vX.Y.Z")
    version = tag[1:]
    expected = {
        PYTHON_ARTIFACT: {
            f"openschichtplaner5_generator-{version}-py3-none-any.whl",
            f"openschichtplaner5_generator-{version}.tar.gz",
        },
        DOCKER_ARTIFACT: {DOCKER_ARCHIVE},
    }
    verified = []
    for artifact, filenames in expected.items():
        directory = artifacts / artifact
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError("Missing artifact directory")
        entries = list(directory.iterdir())
        if ({p.name for p in entries} != filenames | {"SHA256SUMS"}
                or any(p.is_symlink() or not p.is_file() for p in entries)):
            raise ValueError("Unexpected or missing artifact files")
        checksums = {}
        for line in (directory / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
            match = re.fullmatch(r"([0-9a-f]{64})  ([^/\\]+)", line)
            if not match or match[2] not in filenames or match[2] in checksums:
                raise ValueError("Invalid artifact checksum manifest")
            checksums[match[2]] = match[1]
        if checksums.keys() != filenames:
            raise ValueError("Incomplete artifact checksum manifest")
        for filename in sorted(filenames):
            path = directory / filename
            with path.open("rb") as source:
                digest = hashlib.file_digest(source, "sha256").hexdigest()
            if digest != checksums[filename]:
                raise ValueError("Artifact checksum mismatch")
            verified.append((path, digest))
    # Validate every input before creating any output; never replace old staging.
    output.mkdir(parents=True, exist_ok=False)
    manifest = []
    for path, digest in verified:
        shutil.copyfile(path, output / path.name)
        manifest.append(f"{digest}  {path.name}\n")
    (output / "SHA256SUMS").write_text("".join(manifest), encoding="utf-8")
    return [path.name for path, _ in verified]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    names = prepare(args.artifacts, args.output, args.tag)
    print(f"Verified and staged {len(names)} release files and SHA256SUMS")


if __name__ == "__main__":
    main()
