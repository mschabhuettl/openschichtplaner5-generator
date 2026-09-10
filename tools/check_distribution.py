"""Check built distributions in a fresh environment outside the source checkout.

Run after ``python -m build``. Package installation needs the configured package
index (or pip cache); the actual planning and web checks use only synthetic data.
"""

import argparse
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import tomllib
from urllib.error import URLError
from urllib.request import Request, build_opener, ProxyHandler
import venv
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
ASSETS = {
    path.relative_to(ROOT).as_posix()
    for path in (ROOT / "sp5generator" / "static").rglob("*")
    if path.is_file()
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(command, cwd, env, timeout=180):
    completed = subprocess.run(
        [str(part) for part in command], cwd=cwd, env=env,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=timeout,
    )
    if completed.returncode:
        raise RuntimeError(f"Command failed ({completed.returncode}): {command}\n{completed.stdout}")
    return completed.stdout.strip()


def check_wheel(wheel, version):
    with ZipFile(wheel) as archive:
        names = set(archive.namelist())
        require(ASSETS <= names, "Wheel is missing web assets")
        metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
        metadata = BytesParser().parsebytes(archive.read(metadata_name))
        require(metadata["Version"] == version, "Wheel metadata version differs from pyproject.toml")


def check_web(cli, cwd, env, version):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    opener = build_opener(ProxyHandler({}))

    def request(path, payload=None, method=None):
        body = None if payload is None else json.dumps(payload).encode()
        headers = {} if body is None else {"Content-Type": "application/json"}
        with opener.open(Request(base + path, data=body, headers=headers, method=method), timeout=5) as response:
            return response.read()

    with (cwd / "web.log").open("w+") as log:
        process = subprocess.Popen(
            [str(cli), "serve", "--host", "127.0.0.1", "--port", str(port),
             "--state-dir", str(cwd / "web-state")],
            cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                require(process.poll() is None, "Installed web server exited during startup")
                try:
                    if json.loads(request("/healthz")) == {"status": "ok"}:
                        break
                except URLError:
                    pass
                time.sleep(0.2)
            else:
                raise RuntimeError("Installed web server did not become healthy")
            actual = json.loads(request("/api/version"))
            require(actual["version"] == version, "Installed web version mismatch")
            for path in ["/"] + ["/" + asset.removeprefix("sp5generator/") for asset in sorted(ASSETS)]:
                require(len(request(path)) > 0, f"Missing installed web resource: {path}")
            snapshot = json.loads((cwd / "input.json").read_text())
            saved = json.loads(request("/api/snapshots", snapshot, "PUT"))
            job = json.loads(request("/api/jobs", {
                "snapshot_id": saved["id"], "snapshot_revision": saved["revision"], "time_limit": 10,
            }))
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                job = json.loads(request("/api/jobs/" + job["id"]))
                if job["state"] not in ("queued", "running"):
                    break
                time.sleep(0.2)
            require(job["state"] == "succeeded", f"Installed worker did not complete: {job['state']}")
            payload = {"snapshot": saved, "assignments": job["result"]["assignments"]}
            validation = json.loads(request("/api/validate", payload))
            require(validation["valid"] and validation["complete"], "Installed worker produced an invalid plan")
            for format in ("json", "csv", "xlsx"):
                require(len(request("/api/export/" + format, payload)) > 100, f"Empty web export: {format}")
        except Exception:
            log.flush()
            log.seek(0)
            print(log.read(), file=sys.stderr)
            raise
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    distributions = args.dist_dir.resolve()
    wheel = distributions / f"openschichtplaner5_generator-{version}-py3-none-any.whl"
    sdist = distributions / f"openschichtplaner5_generator-{version}.tar.gz"
    require(wheel.is_file() and sdist.is_file(), "Build wheel and sdist with python -m build first")
    check_wheel(wheel, version)
    print(f"Checking distribution {version}: sdist rebuild", flush=True)
    # No inherited source paths or live service configuration in release checks.
    env = {key: value for key, value in os.environ.items()
           if key not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"} and not key.startswith("SP5_")}
    with tempfile.TemporaryDirectory(prefix="sp5-distribution-") as temporary:
        work = Path(temporary)
        source_dir = work / "source"
        source_dir.mkdir()
        with tarfile.open(sdist) as archive:
            archive.extractall(source_dir, filter="data")
        sources = list(source_dir.iterdir())
        require(len(sources) == 1 and sources[0].is_dir(), "Unexpected sdist structure")
        rebuilt = work / "rebuilt"
        run([sys.executable, "-m", "build", "--wheel", "--outdir", rebuilt, sources[0]], work, env)
        rebuilt_wheel = rebuilt / wheel.name
        check_wheel(rebuilt_wheel, version)
        with ZipFile(wheel) as original, ZipFile(rebuilt_wheel) as rebuilt_archive:
            members = {name for name in original.namelist() if name.startswith("sp5generator/")}
            rebuilt_members = {name for name in rebuilt_archive.namelist() if name.startswith("sp5generator/")}
            require(members == rebuilt_members, "Source archive and wheel contain different application paths")
            require(all(original.read(name) == rebuilt_archive.read(name) for name in members),
                    "Source archive and wheel contain different application files")
        environment = work / "venv"
        print("Installing and checking the core package in a fresh environment", flush=True)
        venv.EnvBuilder(with_pip=True).create(environment)
        bin_dir = environment / ("Scripts" if os.name == "nt" else "bin")
        python = bin_dir / ("python.exe" if os.name == "nt" else "python")
        cli = bin_dir / ("sp5-generator.exe" if os.name == "nt" else "sp5-generator")
        run([python, "-m", "pip", "install", "-c", ROOT / "requirements.lock", wheel], work, env)
        run([python, "-m", "pip", "check"], work, env)
        run([python, "-I", "-c", (
            "import importlib.metadata, importlib.util, sp5generator; "
            f"assert sp5generator.__version__ == importlib.metadata.version('openschichtplaner5-generator') == {version!r}; "
            "assert importlib.util.find_spec('sp5lib') is None; "
            "assert importlib.util.find_spec('fastapi') is None"
        )], work, env)
        require(run([cli, "--version"], work, env) == f"sp5-generator {version}", "CLI version mismatch")
        run([cli, "demo", "--days", "2", "-o", "input.json"], work, env)
        run([cli, "solve", "input.json", "--time-limit", "10", "-o", "result.json"], work, env)
        run([cli, "validate", "input.json", "result.json", "-o", "validation.json"], work, env)
        for format in ("csv", "xlsx"):
            run([cli, "export", "input.json", "result.json", f"result.{format}"], work, env)
            require((work / f"result.{format}").stat().st_size > 100, f"Empty CLI export: {format}")
        for model in ("input", "result"):
            schema = json.loads(run([cli, "schema", model], work, env))
            require(schema.get("type") == "object", f"Invalid {model} schema")
        print("Installing web/SP5 extras and checking the installed server and worker", flush=True)
        run([python, "-m", "pip", "install", "-c", ROOT / "requirements-web.lock", f"{wheel}[web,sp5]"], work, env)
        run([python, "-m", "pip", "check"], work, env)
        check_web(cli, work, env, version)
    sums = "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in (wheel, sdist))
    (distributions / "SHA256SUMS").write_text(sums, encoding="utf-8")
    print(f"Distribution {version}: sdist rebuild, clean core/web installs, CLI, assets, worker and exports passed")


if __name__ == "__main__":
    main()
