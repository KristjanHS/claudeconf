#!/usr/bin/env python3
"""Publish the manifest-listed dotfiles files into claudeconf, sanitized.

Source is dotfiles HEAD (never its working tree). Modes: sync (default),
--dry-run (report only), --check (drift; exit 0 when dotfiles is absent).
Plan: docs/plans/2026-09-26-dotfiles-sync-and-statusline-gif.md
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = "sync-manifest.txt"
IGNORE = "sync-ignore.txt"
TERMS = "claudeconf-publish/private-terms.txt"
REWRITES = "claudeconf-publish/rewrites.tsv"
NEVER_SYNC = frozenset({".claude/CLAUDE.md", ".claude/settings.json"})
PROPOSAL_DIRS = tuple(
    f"claude/.claude/{d}/"
    for d in ("hooks", "rules", "references", "lib", "agents", "commands")
)
PROPOSAL_FILES = ("claude/.claude/statusline.sh",)
SKILLS_ROOT = "skills/"

HOME_RE = re.compile(r"/(?:home|Users)/[A-Za-z0-9._-]+/")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
CITE_RE = re.compile(r"\b((?:references|rules)/[A-Za-z0-9._-]+\.md)\b")


class Refused(Exception):
    pass


@dataclass
class Blob:
    sha: str
    executable: bool


@dataclass
class Result:
    changed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    refused: list[tuple[str, str]] = field(default_factory=list)
    drift: list[str] = field(default_factory=list)
    broken: list[str] = field(
        default_factory=list
    )  # config errors: drift in --check, never HELD


def read_list(path: Path) -> list[str]:
    if not path.is_file():
        return []
    lines = (ln.split("#", 1)[0].strip() for ln in path.read_text().splitlines())
    return [ln for ln in lines if ln]


def parse_manifest(root: Path) -> list[tuple[str, str]]:
    pairs = []
    for ln in read_list(root / MANIFEST):
        dst, sep, src = (p.strip() for p in ln.partition("<-"))
        if not sep or not dst or not src or dst.endswith("/") != src.endswith("/"):
            raise SystemExit(f"error: bad manifest line: {ln}")
        pairs.append((dst, src))
    return pairs


class DotfilesHead:
    """Blob lookup over dotfiles HEAD; one ls-tree + one cat-file process."""

    def __init__(self, repo: Path):
        self.repo = repo
        out = self._git("ls-tree", "-r", "-z", "HEAD").decode()
        self.tree: dict[str, Blob] = {}
        for entry in filter(None, out.split("\0")):
            meta, path = entry.split("\t", 1)
            mode, kind, sha = meta.split()
            if kind == "blob":
                self.tree[path] = Blob(sha, mode == "100755")
        self._cache: dict[str, bytes] = {}

    def _git(self, *args: str) -> bytes:
        return subprocess.run(
            ["git", "-C", str(self.repo), *args], capture_output=True, check=True
        ).stdout

    def load(self, paths: list[str]) -> None:
        shas = [self.tree[p].sha for p in paths if p in self.tree]
        if not shas:
            return
        out = subprocess.run(
            ["git", "-C", str(self.repo), "cat-file", "--batch"],
            input="\n".join(shas).encode() + b"\n",
            capture_output=True,
            check=True,
        ).stdout
        pos = 0
        for sha in shas:
            header_end = out.index(b"\n", pos)
            size = int(out[pos:header_end].split()[2])
            self._cache[sha] = out[header_end + 1 : header_end + 1 + size]
            pos = header_end + 1 + size + 1

    def read(self, path: str) -> bytes:
        sha = self.tree[path].sha
        if sha not in self._cache:
            self.load([path])
        return self._cache[sha]


def load_terms(head: DotfilesHead) -> list[str] | None:
    if TERMS not in head.tree:
        return None
    lines = (
        ln.split("#", 1)[0].strip() for ln in head.read(TERMS).decode().splitlines()
    )
    return [ln for ln in lines if ln]


def load_rewrites(head: DotfilesHead) -> list[tuple[re.Pattern[str], str]]:
    if REWRITES not in head.tree:
        return []
    rules = []
    for ln in head.read(REWRITES).decode().splitlines():
        if not ln.strip() or ln.startswith("#"):
            continue
        pattern, _, repl = ln.partition("\t")
        rules.append((re.compile(pattern), repl))
    return rules


def sanitize(
    text: str,
    suffix: str,
    terms: list[str],
    rewrites: Sequence[tuple[re.Pattern[str], str]] = (),
) -> str:
    """Return publishable text or raise Refused naming the first blocking hit."""
    for pattern, repl in rewrites:
        text = pattern.sub(repl, text)
    if HOME_RE.search(text):
        if suffix == ".py":
            raise Refused(f"home path in .py, line {_line(text, HOME_RE.search(text))}")
        text = HOME_RE.sub("$HOME/" if suffix == ".sh" else "~/", text)
    if m := EMAIL_RE.search(text):
        raise Refused(f"email, line {_line(text, m)}")
    for term in terms:
        term_re = re.compile(
            rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])", re.I
        )
        if m := term_re.search(text):
            raise Refused(f"private term '{term}', line {_line(text, m)}")
    return text


def _line(text: str, m: re.Match[str] | None) -> int:
    return text.count("\n", 0, m.start()) + 1 if m else 0


def expand(head: DotfilesHead, pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Manifest pairs -> per-file (dst, src); a missing src maps to ('', src)."""
    files = []
    for dst, src in pairs:
        if src.endswith("/"):
            hits = sorted(p for p in head.tree if p.startswith(src))
            files += [(dst + p[len(src) :], p) for p in hits] or [("", src)]
        else:
            files.append((dst, src) if src in head.tree else ("", src))
    return files


def covered(path: str, entries: list[str]) -> bool:
    return any(path == e or (e.endswith("/") and path.startswith(e)) for e in entries)


def proposals(
    head: DotfilesHead, pairs: list[tuple[str, str]], ignored: list[str]
) -> list[str]:
    listed = [src for _, src in pairs] + ignored
    units = {p for p in head.tree if p.startswith(PROPOSAL_DIRS) or p in PROPOSAL_FILES}
    units |= {
        SKILLS_ROOT + p[len(SKILLS_ROOT) :].split("/", 1)[0] + "/"
        for p in head.tree
        if p.startswith(SKILLS_ROOT) and p.count("/") >= 2
    }
    return sorted(u for u in units if not covered(u, listed))


def run(root: Path, dotfiles: Path, mode: str) -> tuple[Result, list[str], list[str]]:
    head = DotfilesHead(dotfiles)
    pairs = parse_manifest(root)
    files = expand(head, pairs)
    head.load([src for _, src in files if src in head.tree])
    terms = load_terms(head)
    rewrites = load_rewrites(head)
    published = {dst for dst, _ in files if dst}
    res, cites = Result(), set()

    for dst, src in files:
        if not dst:
            res.refused.append((src, "missing in dotfiles HEAD"))
            res.broken.append(src)
            continue
        if dst in NEVER_SYNC:
            res.refused.append((dst, "NEVER_SYNC teaching skeleton"))
            res.broken.append(dst)
            continue
        if terms is None:
            res.refused.append((dst, f"{TERMS} missing in dotfiles HEAD (fail closed)"))
            res.broken.append(dst)
            continue
        try:
            raw = head.read(src).decode()
        except UnicodeDecodeError:
            res.refused.append((dst, "not utf-8"))
            continue
        try:
            text = sanitize(raw, Path(dst).suffix, terms, rewrites)
        except Refused as exc:
            res.refused.append((dst, str(exc)))
            continue
        cites |= {
            (dst, c) for c in CITE_RE.findall(text) if f".claude/{c}" not in published
        }

        target = root / dst
        want_exec = head.tree[src].executable
        same = (
            target.is_file()
            and target.read_bytes() == text.encode()
            and bool(target.stat().st_mode & 0o100) == want_exec
        )
        if same:
            res.unchanged.append(dst)
            continue
        res.changed.append(dst)
        if mode == "check":
            res.drift.append(dst)
        elif mode == "sync":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(text.encode())
            target.chmod(0o755 if want_exec else 0o644)

    props = proposals(head, pairs, read_list(root / IGNORE)) if mode != "check" else []
    advisories = (
        sorted(f"{c} (cited by {d})" for d, c in cites) if mode != "check" else []
    )
    return res, props, advisories


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Publish dotfiles files into claudeconf.")
    group = ap.add_mutually_exclusive_group()
    group.add_argument(
        "--check", action="store_true", help="report drift, write nothing"
    )
    group.add_argument(
        "--dry-run", action="store_true", help="report changes, write nothing"
    )
    ap.add_argument("--root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    mode = "check" if args.check else "dry-run" if args.dry_run else "sync"
    dotfiles = Path(os.environ.get("DOTFILES") or args.root.parent / "dotfiles")

    if not (dotfiles / ".git").exists():
        if mode == "check":
            print(f"drift: skipped (no dotfiles repo at {dotfiles})")
            return 0
        print(f"error: no dotfiles repo at {dotfiles} (set DOTFILES)", file=sys.stderr)
        return 2

    res, props, advisories = run(args.root, dotfiles, mode)
    verb = {"sync": "wrote", "dry-run": "would write", "check": "DRIFT"}[mode]
    for dst in res.changed:
        print(f"{verb} {dst}")
    for dst, why in res.refused:
        held = mode == "check" and dst not in res.broken
        print(f"{'HELD' if held else 'REFUSED'} {dst}: {why}")
    for p in props:
        print(f"not published — add to manifest? {p}")
    for a in advisories:
        print(f"advisory: dangling cite {a}")

    if mode == "check":
        n_held = len(res.refused) - len(res.broken)
        print(
            f"drift: {len(res.drift)} drifted, {n_held} held, {len(res.broken)} broken"
        )
        return 1 if res.drift or res.broken else 0
    print(
        f"sync: {len(res.changed)} changed, {len(res.unchanged)} unchanged, "
        f"{len(res.refused)} refused"
    )
    return 1 if res.refused else 0


if __name__ == "__main__":
    sys.exit(main())
