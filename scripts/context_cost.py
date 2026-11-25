#!/usr/bin/env python3
"""Measured context-cost block: every number parsed from the repo's own files.

Usage: context_cost.py --readme FILE [--root DIR] [--check].
Writes the table between the context-cost markers in FILE; `--check` writes
nothing. Exit 0 ok/fresh, 1 stale block (--check), 2 input error — a missing
source file or a regex that no longer matches is an error, never a guessed value.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Sibling import that survives `python3 -I` and by-path importlib loads (tests).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from marker_block import MarkerError, has_markers, replace_between  # noqa: E402

BLOCK_MARKERS = ("<!-- context-cost:start -->", "<!-- context-cost:end -->")
BYTES_PER_TOKEN = 4

STATUSLINE = ".claude/statusline.sh"
BUDGET_HOOK = ".claude/hooks/impag-budget-check.py"
# name -> (source file, regex with one integer group)
PARSED: dict[str, tuple[str, str]] = {
    "window": (STATUSLINE, r"^WINDOW=(\d+)$"),
    "hard_stop": (BUDGET_HOOK, r"^HARD_STOP_TOKENS = ([\d_]+)$"),
}
BANDS_RE = re.compile(r"^BANDS: .*?= \($(.*?)^\)$", re.M | re.S)
SOFT_RE = re.compile(r'\(\s*([\d_]+),\s*"soft"')


class InputError(Exception):
    """Bad input: exit 2."""


@dataclass(frozen=True)
class Row:
    metric: str
    value: str


def _read(root: Path, rel: str) -> str:
    try:
        return (root / rel).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise InputError(f"cannot read {root / rel}: {e}") from e


def _md_files(root: Path, rel: str) -> list[Path]:
    d = root / rel
    if not d.is_dir():
        raise InputError(f"missing directory {d}")
    return sorted(p for p in d.glob("*.md") if p.is_file())


def _int(root: Path, rel: str, pattern: str) -> int:
    hits = re.findall(pattern, _read(root, rel), re.M)
    if len(hits) != 1:
        raise InputError(f"{rel}: /{pattern}/ matched {len(hits)} times, need 1")
    return int(hits[0].replace("_", ""))


def _soft_bands(root: Path) -> list[int]:
    block = BANDS_RE.search(_read(root, BUDGET_HOOK))
    bands = (
        [int(b.replace("_", "")) for b in SOFT_RE.findall(block[1])] if block else []
    )
    if not bands:
        raise InputError(f"{BUDGET_HOOK}: no soft entries in BANDS")
    return bands


def _n(v: int) -> str:
    return f"{v:,}"


def collect(root: Path) -> list[Row]:
    rules = _md_files(root, ".claude/rules")
    refs = _md_files(root, ".claude/references")
    deferred = sum(p.stat().st_size for p in rules + refs)
    claude_b = len(_read(root, ".claude/CLAUDE.md").encode("utf-8"))
    v = {k: _int(root, rel, pat) for k, (rel, pat) in PARSED.items()}
    soft = _soft_bands(root)
    for kind in ("skills", "hooks"):
        if not (root / ".claude" / kind).is_dir():
            raise InputError(f"missing directory {root / '.claude' / kind}")
    skill_dir = root / ".claude/skills"
    skills = sum(1 for p in skill_dir.iterdir() if p.is_dir() and p.name[0] != ".")
    hook_dir = root / ".claude/hooks"
    hooks = sum(1 for p in hook_dir.iterdir() if p.suffix in (".py", ".sh"))
    return [
        Row(
            "Always loaded: `CLAUDE.md`",
            f"{_n(claude_b)} bytes (~{_n(claude_b // BYTES_PER_TOKEN)} tokens)",
        ),
        Row("Path-gated rules", _n(len(rules))),
        Row("References", _n(len(refs))),
        Row("On demand: rules + references", f"{_n(deferred)} bytes"),
        Row("Statusline budget window", f"{_n(v['window'])} tokens"),
        Row("Budget soft bands", " / ".join(map(_n, soft)) + " tokens"),
        Row("Budget hard stop", f"{_n(v['hard_stop'])} tokens"),
        Row("Skills", _n(skills)),
        Row("Hooks", _n(hooks)),
    ]


def _row(cells: list[str]) -> str:
    """GFM splits a cell on `|` even inside backticks, so escape it."""
    return "| " + " | ".join(c.replace("|", r"\|") for c in cells) + " |"


def render_block(rows: list[Row], command: str) -> str:
    lines = ["| Metric | Value |", "|---|---|"]
    lines += [_row([r.metric, r.value]) for r in rows]
    lines += ["", f"Regenerate: `{command}`"]
    return "\n".join(lines) + "\n"


def command_for(readme: Path, root: Path) -> str:
    """The write command as run from the repo root — stable whatever the caller's cwd."""
    try:
        rel = readme.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = str(readme)
    return f"python3 scripts/context_cost.py --readme {rel}"


def run(readme: Path, root: Path, check: bool) -> int:
    try:
        text = readme.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise InputError(f"cannot read {readme}: {e}") from e
    if not has_markers(text, BLOCK_MARKERS):
        raise InputError(f"{readme}: no {BLOCK_MARKERS[0]} markers")
    try:
        replace_between(text, *BLOCK_MARKERS, "")  # validates the pair only
    except MarkerError as e:
        raise InputError(f"{readme}: {e}") from e
    block = render_block(collect(root), command_for(readme, root))
    fresh = replace_between(text, *BLOCK_MARKERS, block)
    if fresh == text:
        return 0
    if check:
        print(f"stale: {readme}", file=sys.stderr)
        return 1
    try:
        readme.write_bytes(fresh.encode("utf-8"))
    except OSError as e:
        raise InputError(f"cannot write {readme}: {e}") from e
    print(f"updated: {readme}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Measured context-cost block for a README."
    )
    ap.add_argument("--readme", required=True, type=Path)
    ap.add_argument(
        "--root", type=Path, default=Path("."), help="repo root (default: cwd)"
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if the block is stale; write nothing",
    )
    args = ap.parse_args(argv)
    try:
        return run(args.readme, args.root, args.check)
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
