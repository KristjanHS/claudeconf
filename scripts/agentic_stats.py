#!/usr/bin/env python3
"""Fold-proof portfolio stats: per-repo markdown blocks computed from each repo's HEAD tree.

Usage: agentic_stats.py --config PATH [--repo NAME ...]. Exit 0 ok, 2 input error.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# lang -> (pathspec globs, git grep -E regex)
LANGS: dict[str, tuple[list[str], str]] = {
    "ts": (["*.test.ts", "*.test.tsx", "*.spec.ts", "*.test.js"], r"^\s*(it|test)\("),
    "py": (["test_*.py", "*/test_*.py", "*_test.py"], r"^\s*(async\s+)?def test_"),
    "go": (["*_test.go"], r"^func Test\w*\("),
}
DEFAULT_EXCLUDE = [".claude"]
ALLOWED_KEYS = {
    "name",
    "path",
    "langs",
    "exclude",
    "release_pattern",
    "release_exclude",
    "adr_glob",
    "prod_since",
    "upstream_ref",
    "upstream_name",
    "hub",
}
ABSENT = "—"


class InputError(Exception):
    """Bad config or repo state; main() maps it to exit 2."""


@dataclass
class Repo:
    name: str
    path: Path
    langs: list[str]
    exclude: list[str] = field(default_factory=list)
    release_pattern: list[str] = field(default_factory=list)
    release_exclude: list[str] = field(default_factory=list)
    adr_glob: str | None = None
    prod_since: str | None = None
    upstream_ref: str | None = None
    upstream_name: str | None = None
    hub: bool = False


@dataclass
class Row:
    metric: str
    value: str
    definition: str


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True
    )


def load_config(path: Path) -> list[Repo]:
    try:
        data = tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise InputError(f"cannot read config {path}: {e}") from e
    entries = data.get("repo")
    if not isinstance(entries, list) or not entries:
        raise InputError(f"{path}: no [[repo]] entries")
    repos = []
    for entry in entries:
        unknown = set(entry) - ALLOWED_KEYS
        if unknown:
            raise InputError(f"{path}: unknown key(s) {sorted(unknown)}")
        if "name" not in entry or "path" not in entry:
            raise InputError(f"{path}: every [[repo]] needs name and path")
        repo_path = Path(entry["path"]).expanduser()
        if not repo_path.is_absolute():
            repo_path = (path.parent / repo_path).resolve()
        if _git(repo_path, "rev-parse", "--verify", "-q", "HEAD").returncode != 0:
            raise InputError(
                f"{entry['name']}: not a git repo with a HEAD: {entry['path']}"
            )
        langs = entry.get("langs", [])
        bad = [lang for lang in langs if lang not in LANGS]
        if bad:
            raise InputError(
                f"{entry['name']}: unknown lang(s) {bad}; known: {sorted(LANGS)}"
            )
        fields = {k: v for k, v in entry.items() if k != "path"}
        repos.append(Repo(path=repo_path, **fields))
    return repos


def count_tests(
    repo: Path, langs: list[str], exclude: list[str], rev: str = "HEAD"
) -> int:
    total = 0
    excludes = [f":(exclude){p}" for p in DEFAULT_EXCLUDE + exclude]
    for lang in langs:
        globs, regex = LANGS[lang]
        res = _git(repo, "grep", "-c", "-E", regex, rev, "--", *globs, *excludes)
        if res.returncode > 1:
            raise InputError(f"git grep failed in {repo}: {res.stderr.strip()}")
        for line in res.stdout.splitlines():
            total += int(line.rsplit(":", 1)[1])
    return total


def tests_definition(langs: list[str]) -> str:
    parts = [
        f"`{LANGS[lang][1]}` in {', '.join(f'`{g}`' for g in LANGS[lang][0])}"
        for lang in langs
    ]
    return "static count of lines matching " + "; ".join(parts) + " at HEAD"


def collect(repo: Repo) -> list[Row]:
    tests = (
        str(count_tests(repo.path, repo.langs, repo.exclude)) if repo.langs else ABSENT
    )
    return [
        Row(
            "Tests",
            tests,
            tests_definition(repo.langs) if repo.langs else "no test langs configured",
        )
    ]


def render_block(rows: list[Row]) -> str:
    lines = ["| Metric | Value | Definition |", "|---|---|---|"]
    lines += [f"| {r.metric} | {r.value} | {r.definition} |" for r in rows]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fold-proof portfolio stats per repo.")
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument(
        "--repo", action="append", default=[], help="only this repo name (repeatable)"
    )
    args = ap.parse_args(argv)
    try:
        repos = load_config(args.config)
        unknown = set(args.repo) - {r.name for r in repos}
        if unknown:
            raise InputError(f"--repo not in config: {sorted(unknown)}")
        for repo in repos:
            if args.repo and repo.name not in args.repo:
                continue
            print(f"### {repo.name}\n\n{render_block(collect(repo))}")
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
