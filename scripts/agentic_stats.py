#!/usr/bin/env python3
"""Fold-proof portfolio stats: per-repo markdown blocks computed from each repo's HEAD tree.

Usage: agentic_stats.py --config PATH [--repo NAME ...] [--hub FILE] [--check].
Exit 0 ok/fresh, 1 stale block (--check), 2 input error.
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

# Sibling import that survives `python3 -I` and by-path importlib loads (tests).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from marker_block import MarkerError, has_markers, replace_between  # noqa: E402

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
SCC_MISSING = "scc not on PATH — install scc; refusing to report 0 lines"
PROD_SINCE_RE = re.compile(r"^\d{4}-\d{2}$")
PROD_DEFINITION = "first production deploy (manual)"
NOT_TRACKED = "not tracked"
LIST_KEYS = {"langs", "exclude", "release_pattern", "release_exclude"}
BOOL_KEYS = {"hub"}
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
    "url",
}
ABSENT = "—"
BLOCK_MARKERS = ("<!-- agentic-stats:start -->", "<!-- agentic-stats:end -->")
HUB_MARKERS = ("<!-- agentic-portfolio:start -->", "<!-- agentic-portfolio:end -->")
HUB_COLS = ["Tests", "CI gates", "ADRs", "Releases", "Lines", "In prod since"]


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
    url: str | None = None


@dataclass
class Row:
    metric: str
    value: str
    definition: str


def _git(repo: Path, *args: str, text: bool = True) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=text
        )
    except OSError as e:
        raise InputError(f"cannot run git: {e}") from e


def _check_types(entry: dict, where: Path) -> None:
    label = entry.get("name", "?")
    for key, value in entry.items():
        if key in LIST_KEYS:
            ok, kind = (
                isinstance(value, list) and all(isinstance(v, str) for v in value),
                "a list of strings",
            )
        elif key in BOOL_KEYS:
            ok, kind = isinstance(value, bool), "true/false"
        else:
            ok, kind = isinstance(value, str), "a string"
        if not ok:
            raise InputError(f"{where}: {label}: {key} must be {kind}, got {value!r}")


def load_config(path: Path) -> list[Repo]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
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
        _check_types(entry, path)
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


def _excl(exclude: list[str]) -> str:
    return ", ".join(f"`{p}`" for p in DEFAULT_EXCLUDE + exclude)


def tests_definition(langs: list[str], exclude: list[str]) -> str:
    parts = [
        f"`{LANGS[lang][1]}` in {', '.join(f'`{g}`' for g in LANGS[lang][0])}"
        for lang in langs
    ]
    return (
        f"static count: lines matching {'; '.join(parts)} at HEAD,"
        f" excl. {_excl(exclude)}; `.each`/parametrized cases count once"
    )


def loc_definition(exclude: list[str]) -> str:
    return (
        "scc code lines (no blanks/comments) at HEAD,"
        f" excl. docs/data formats, {_excl(exclude)}"
    )


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
    archive = _git(
        repo, "archive", "--format=tar", rev, "--", ".", *excludes, text=False
    )
    if archive.returncode != 0:
        raise InputError(
            f"git archive failed in {repo}: {archive.stderr.decode().strip()}"
        )
    with tempfile.TemporaryDirectory() as tmp:
        try:
            with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
                # symlinks carry no code lines; an absolute target would trip filter="data"
                files = [m for m in tar.getmembers() if not m.issym()]
                tar.extractall(tmp, members=files, filter="data")
        except tarfile.TarError as e:
            raise InputError(f"cannot unpack git archive of {repo}: {e}") from e
        res = subprocess.run(
            [scc, "--format", "json", "--no-cocomo", tmp],
            capture_output=True,
            text=True,
        )
    if res.returncode != 0:
        raise InputError(f"scc failed on {repo}: {res.stderr.strip()}")
    try:
        return sum(
            lang["Code"]
            for lang in json.loads(res.stdout)
            if lang["Name"] not in LOC_SKIP_LANGS
        )
    except (ValueError, KeyError, TypeError) as e:
        raise InputError(f"unexpected scc output on {repo}: {e!r}") from e


def _upstream_delta(repo: Repo, count) -> str:
    """`count(rev)` at HEAD, or `+N over <upstream>` when the repo sets upstream_ref."""
    if not repo.upstream_ref:
        return str(count("HEAD"))
    ref = repo.upstream_ref
    if _git(repo.path, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}").returncode:
        raise InputError(f"{repo.name}: upstream_ref {ref!r} does not resolve")
    return f"{count('HEAD') - count(ref):+d} over {repo.upstream_name or ref}"


def collect(repo: Repo) -> list[Row]:
    baseline = repo.upstream_name or repo.upstream_ref
    delta_note = f" (delta vs {baseline})" if repo.upstream_ref else ""
    if repo.langs:
        tests = _upstream_delta(
            repo, lambda rev: count_tests(repo.path, repo.langs, repo.exclude, rev)
        )
        tests_def = tests_definition(repo.langs, repo.exclude) + delta_note
    else:
        tests, tests_def = ABSENT, NOT_TRACKED
    if repo.release_pattern:
        releases = str(
            count_releases(repo.path, repo.release_pattern, repo.release_exclude)
        )
        releases_def = releases_definition(repo.release_pattern, repo.release_exclude)
    else:
        releases, releases_def = ABSENT, NOT_TRACKED
    return [
        Row("Tests", tests, tests_def),
        Row("CI gates", str(count_ci_gates(repo.path)), CI_DEFINITION),
        Row("Releases", releases, releases_def),
        Row(
            "ADRs",
            str(count_adrs(repo.path, repo.adr_glob)) if repo.adr_glob else ABSENT,
            f"files matching `{repo.adr_glob}`" if repo.adr_glob else NOT_TRACKED,
        ),
        Row(
            "Lines",
            _upstream_delta(repo, lambda rev: count_loc(repo.path, repo.exclude, rev)),
            loc_definition(repo.exclude) + delta_note,
        ),
        Row("In prod since", repo.prod_since or ABSENT, PROD_DEFINITION),
    ]


def _row(cells: list[str]) -> str:
    """GFM splits a cell on `|` even inside backticks, so escape it."""
    return "| " + " | ".join(c.replace("|", r"\|") for c in cells) + " |"


def render_block(rows: list[Row]) -> str:
    lines = ["| Metric | Value | Definition |", "|---|---|---|"]
    lines += [_row([r.metric, r.value, r.definition]) for r in rows]
    return "\n".join(lines) + "\n"


def render_hub(stats: list[tuple[Repo, list[Row]]]) -> str:
    lines = [
        "| Repo | " + " | ".join(HUB_COLS) + " |",
        "|---" * (len(HUB_COLS) + 1) + "|",
    ]
    defs: dict[str, dict[str, list[str]]] = {col: {} for col in HUB_COLS}
    for repo, rows in stats:
        by_metric = {r.metric: r for r in rows}
        name = f"[{repo.name}]({repo.url})" if repo.url else repo.name
        lines.append(_row([name] + [by_metric[c].value for c in HUB_COLS]))
        for col in HUB_COLS:
            defs[col].setdefault(by_metric[col].definition, []).append(repo.name)
    lines.append("")
    for col in HUB_COLS:
        if len(defs[col]) == 1:
            lines.append(f"- **{col}**: {next(iter(defs[col]))}")
        else:
            lines.append(f"- **{col}**:")
            lines += [f"  - {', '.join(n)}: {d}" for d, n in defs[col].items()]
    return "\n".join(lines) + "\n"


def check_repo_block(repo: Repo, rows: list[Row]) -> bool:
    """True when the repo README's block is fresh (or the README has no markers)."""
    readme = repo.path / "README.md"
    try:
        text = readme.read_bytes().decode("utf-8") if readme.exists() else ""
    except (OSError, UnicodeDecodeError) as e:
        raise InputError(f"cannot read {readme}: {e}") from e
    if not has_markers(text, BLOCK_MARKERS):
        print(f"skip: {repo.name} has no agentic-stats markers", file=sys.stderr)
        return True
    try:
        fresh = replace_between(text, *BLOCK_MARKERS, render_block(rows))
    except MarkerError as e:
        raise InputError(f"{readme}: {e}") from e
    if fresh != text:
        print(f"stale: {readme}", file=sys.stderr)
        return False
    return True


def run_hub(hub: Path, repos: list[Repo], check: bool) -> int:
    try:
        text = hub.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise InputError(f"cannot read hub {hub}: {e}") from e
    body = render_hub([(r, collect(r)) for r in repos if r.hub])
    try:
        fresh = replace_between(text, *HUB_MARKERS, body)
    except MarkerError as e:
        raise InputError(f"{hub}: {e}") from e
    if fresh == text:
        return 0
    if check:
        print(f"stale: {hub}", file=sys.stderr)
        return 1
    try:
        hub.write_bytes(fresh.encode("utf-8"))
    except OSError as e:
        raise InputError(f"cannot write hub {hub}: {e}") from e
    print(f"updated: {hub}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fold-proof portfolio stats per repo.")
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument(
        "--repo", action="append", default=[], help="only this repo name (repeatable)"
    )
    ap.add_argument("--hub", type=Path, help="write the portfolio table into FILE")
    ap.add_argument(
        "--check", action="store_true", help="exit 1 if a block is stale; write nothing"
    )
    args = ap.parse_args(argv)
    try:
        repos = load_config(args.config)
        unknown = set(args.repo) - {r.name for r in repos}
        if unknown:
            raise InputError(f"--repo not in config: {sorted(unknown)}")
        if args.hub:
            if args.repo:
                raise InputError("--hub renders the whole portfolio; drop --repo")
            return run_hub(args.hub, repos, args.check)
        stale = False
        for repo in repos:
            if args.repo and repo.name not in args.repo:
                continue
            rows = collect(repo)
            if args.check:
                stale |= not check_repo_block(repo, rows)
            else:
                print(f"### {repo.name}\n\n{render_block(rows)}")
    except (InputError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
