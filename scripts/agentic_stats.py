#!/usr/bin/env python3
"""Fold-proof portfolio stats: per-repo markdown blocks computed from each repo's HEAD tree.

Usage: agentic_stats.py --config PATH [--repo NAME ...]. Exit 0 ok, 2 input error.
"""

from __future__ import annotations

import argparse
import fnmatch
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# lang -> (pathspec globs, git grep -E regex)
LANGS: dict[str, tuple[list[str], str]] = {
    "ts": (["*.test.ts", "*.test.tsx", "*.spec.ts", "*.test.js"], r"^\s*(it|test)\("),
    "py": (["test_*.py", "*/test_*.py", "*_test.py"], r"^\s*(async\s+)?def test_"),
    "go": (["*_test.go"], r"^func Test\w*\("),
}
DEFAULT_EXCLUDE = [".claude"]
GATE_TRIGGERS = {"push", "pull_request", "merge_group"}
CI_DEFINITION = (
    "workflows triggered on push / pull_request / merge_group;"
    " schedule- or dispatch-only ops jobs excluded"
)
LOC_SKIP_LANGS = {"Markdown", "Plain Text", "JSON", "CSV", "SVG", "License"}
LOC_DEFINITION = (
    "scc code lines (no blanks/comments) at HEAD,"
    " excl. docs/data formats and vendored dirs"
)
SCC_MISSING = "scc not on PATH — install scc; refusing to report 0 lines"
PROD_SINCE_RE = re.compile(r"^\d{4}-\d{2}$")
PROD_DEFINITION = "first production deploy (manual)"
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
    langs: list[str] = field(default_factory=list)
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
        prod = entry.get("prod_since")
        if prod is not None and not (
            isinstance(prod, str) and PROD_SINCE_RE.match(prod)
        ):
            raise InputError(
                f"{entry['name']}: prod_since must be 'YYYY-MM', got {prod!r}"
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


def _workflow_triggers(doc: object) -> set[str]:
    if not isinstance(doc, dict):
        raise ValueError("top level is not a mapping")
    # YAML 1.1 parses a bare `on:` key as boolean True
    on = doc.get("on", doc.get(True))
    if isinstance(on, str):
        return {on}
    if isinstance(on, list):
        return {str(t) for t in on}
    if isinstance(on, dict):
        return {str(t) for t in on}
    return set()


def count_ci_gates(repo: Path) -> int:
    res = _git(repo, "ls-tree", "-r", "--name-only", "HEAD", "--", ".github/workflows")
    gates = 0
    for name in res.stdout.splitlines():
        if not name.endswith((".yml", ".yaml")):
            continue
        body = _git(repo, "show", f"HEAD:{name}").stdout
        try:
            triggers = _workflow_triggers(yaml.safe_load(body))
        except (yaml.YAMLError, ValueError) as e:
            raise InputError(f"{repo}: malformed workflow {name}: {e}") from e
        if triggers & GATE_TRIGGERS:
            gates += 1
    return gates


def count_releases(repo: Path, pattern: list[str], exclude: list[str]) -> int:
    tags = _git(repo, "tag", "-l", *pattern).stdout.splitlines()
    return sum(1 for t in tags if not any(fnmatch.fnmatchcase(t, x) for x in exclude))


def releases_definition(pattern: list[str], exclude: list[str]) -> str:
    text = "git tags matching " + ", ".join(f"`{p}`" for p in pattern)
    if exclude:
        text += " excluding " + ", ".join(f"`{x}`" for x in exclude)
    return text


def count_adrs(repo: Path, adr_glob: str) -> int:
    names = _git(repo, "ls-tree", "-r", "--name-only", "HEAD").stdout.splitlines()
    return sum(1 for n in names if fnmatch.fnmatchcase(n, adr_glob))


def count_loc(repo: Path, exclude: list[str], rev: str = "HEAD") -> int:
    scc = shutil.which("scc")
    if scc is None:
        raise InputError(SCC_MISSING)
    excludes = [f":(exclude){p}" for p in DEFAULT_EXCLUDE + exclude]
    archive = subprocess.run(
        ["git", "-C", str(repo), "archive", "--format=tar", rev, "--", ".", *excludes],
        capture_output=True,
    )
    if archive.returncode != 0:
        raise InputError(
            f"git archive failed in {repo}: {archive.stderr.decode().strip()}"
        )
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
            tar.extractall(tmp, filter="data")
        res = subprocess.run(
            [scc, "--format", "json", "--no-cocomo", tmp],
            capture_output=True,
            text=True,
        )
    if res.returncode != 0:
        raise InputError(f"scc failed on {repo}: {res.stderr.strip()}")
    return sum(
        lang["Code"]
        for lang in json.loads(res.stdout)
        if lang["Name"] not in LOC_SKIP_LANGS
    )


def _upstream_delta(repo: Repo, count) -> str:
    """`count(rev)` at HEAD, or `+N over <upstream>` when the repo sets upstream_ref."""
    if not repo.upstream_ref:
        return str(count("HEAD"))
    ref = repo.upstream_ref
    if _git(repo.path, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}").returncode:
        raise InputError(f"{repo.name}: upstream_ref {ref!r} does not resolve")
    return f"{count('HEAD') - count(ref):+d} over {repo.upstream_name or ref}"


def collect(repo: Repo) -> list[Row]:
    delta_note = f" (delta vs `{repo.upstream_ref}`)" if repo.upstream_ref else ""
    if repo.langs:
        tests = _upstream_delta(
            repo, lambda rev: count_tests(repo.path, repo.langs, repo.exclude, rev)
        )
        tests_def = tests_definition(repo.langs) + delta_note
    else:
        tests, tests_def = ABSENT, "no test langs configured"
    if repo.release_pattern:
        releases = str(
            count_releases(repo.path, repo.release_pattern, repo.release_exclude)
        )
        releases_def = releases_definition(repo.release_pattern, repo.release_exclude)
    else:
        releases, releases_def = ABSENT, "no release tag pattern configured"
    return [
        Row("Tests", tests, tests_def),
        Row("CI gates", str(count_ci_gates(repo.path)), CI_DEFINITION),
        Row("Releases", releases, releases_def),
        Row(
            "ADRs",
            str(count_adrs(repo.path, repo.adr_glob)) if repo.adr_glob else ABSENT,
            f"files matching `{repo.adr_glob}`"
            if repo.adr_glob
            else "no ADR glob configured",
        ),
        Row(
            "Lines",
            _upstream_delta(repo, lambda rev: count_loc(repo.path, repo.exclude, rev)),
            LOC_DEFINITION + delta_note,
        ),
        Row("In prod since", repo.prod_since or ABSENT, PROD_DEFINITION),
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
