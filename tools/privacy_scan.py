"""Check changes or files for private data before pushing or publishing.

Reports only paths, counts and rule names. Matched text is never printed, so the
output stays safe to paste into a log. A private name list (one entry per line,
kept outside every worktree) can be passed with --names.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

BLOCKED_SUFFIXES = {".dbf", ".cdx", ".csv", ".xlsx", ".xls", ".sqlite", ".sqlite3",
                    ".db", ".mdb", ".bak", ".env", ".pfx", ".p12", ".key", ".pem"}
# Loopback and documentation hosts are not private; only reachable LAN targets are.
PATTERNS = {
    "private_host": re.compile(r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"
                               r"|\b192\.168\.\d{1,3}\.\d{1,3}\b"
                               r"|\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b"),
    # Only quoted literals; assignments from code expressions are not credentials.
    "credential": re.compile(r"(?i)\b(?:password|passwd|api[_-]?key|secret|token)\s*[:=]\s*"
                             r"[\"'][A-Za-z0-9/+_.-]{12,}[\"']"),
    "bearer_token": re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._-]{16,}"),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[A-Za-z]{2,}\b"),
    "austrian_ssn": re.compile(r"\b\d{4}\s?(?:0[1-9]|[12]\d|3[01])(?:0[1-9]|1[0-2])\d{2}\b"),
}
ALLOWED_EMAILS = re.compile(r"(?i)@(?:example\.(?:com|org|net)|users\.noreply\.github\.com)\b")


def changed_paths(rev_range):
    out = subprocess.run(["git", "diff", "--name-only", "--diff-filter=d", rev_range],
                         capture_output=True, text=True, check=True).stdout
    return [Path(line) for line in out.splitlines() if line]


def collect(paths):
    """Walk the given files and directories, skipping anything git ignores."""
    for path in paths:
        if path.is_file():
            yield path
            continue
        if not path.is_dir():
            continue
        candidates = [p for p in path.rglob("*") if p.is_file() and ".git" not in p.parts]
        absolute = [str(p.resolve()) for p in candidates]
        ignored = set(subprocess.run(["git", "-C", str(path), "check-ignore", "--stdin"],
                                     input="\n".join(absolute),
                                     capture_output=True, text=True).stdout.splitlines())
        yield from (p for p, full in zip(candidates, absolute) if full not in ignored)


def scan(path, names):
    hits = []
    if path.suffix.lower() in BLOCKED_SUFFIXES:
        hits.append(("blocked_suffix", 1))
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return hits
    for rule, pattern in PATTERNS.items():
        found = [m.group(0) for m in pattern.finditer(text)]
        if rule == "email":
            found = [m for m in found if not ALLOWED_EMAILS.search(m)]
        if found:
            hits.append((rule, len(found)))
    matched = sum(text.count(name) for name in names)
    if matched:
        hits.append(("private_name_list", matched))
    return hits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--range", help="git revision range, e.g. origin/main..HEAD")
    parser.add_argument("--paths", nargs="*", type=Path, default=[],
                        help="extra files or directories, e.g. dist/ or a build context")
    parser.add_argument("--names", type=Path,
                        help="private name list outside the worktree, one entry per line")
    args = parser.parse_args()

    names = []
    if args.names:
        names = [line.strip() for line in args.names.read_text(encoding="utf-8").splitlines()
                 if len(line.strip()) > 2]
    targets = list(collect(args.paths))
    if args.range:
        targets += [p for p in changed_paths(args.range) if p.is_file()]
    if not targets:
        print("privacy scan: nothing to check")
        return 0

    findings = {path: hits for path in sorted(set(targets)) if (hits := scan(path, names))}
    print(f"privacy scan: {len(targets)} files checked, "
          f"{len(names)} private names loaded, {len(findings)} files with hits")
    for path, hits in findings.items():
        print(f"  {path}: " + ", ".join(f"{rule}×{count}" for rule, count in hits))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
