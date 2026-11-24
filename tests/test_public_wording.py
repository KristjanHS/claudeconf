"""Public docs (README.md, ADOPT.md, docs/*.md — not docs/plans) carry no "fold"
wording and no private term.

Terms come from `$DOTFILES/claudeconf-publish/private-terms.txt`
(`$DOTFILES` defaults to the sibling `../dotfiles`, as `sync_from_dotfiles.py`
resolves it); the test skips when that file is absent. A hit is reported as
`file:line term #N` — the term itself is never printed.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from conftest import REPO_ROOT

FOLD = re.compile(r"\bfold(s|ed|ing)?\b", re.I)
TERMS_REL = Path("claudeconf-publish") / "private-terms.txt"


def public_docs() -> list[Path]:
    return [
        REPO_ROOT / "README.md",
        REPO_ROOT / "ADOPT.md",
        *sorted((REPO_ROOT / "docs").glob("*.md")),
    ]


def terms_file() -> Path:
    dotfiles = os.environ.get("DOTFILES") or REPO_ROOT.parent / "dotfiles"
    return Path(dotfiles) / TERMS_REL


def load_terms(path: Path) -> list[str]:
    lines = (ln.split("#", 1)[0].strip() for ln in path.read_text().splitlines())
    return [ln for ln in lines if ln]


def term_hits(text: str, terms: list[str]) -> list[tuple[int, int]]:
    """(line, 1-based term index) per hit; same boundary rule as sync's sanitize."""
    hits = []
    for idx, term in enumerate(terms, 1):
        term_re = re.compile(
            rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])", re.I
        )
        for m in term_re.finditer(text):
            hits.append((text.count("\n", 0, m.start()) + 1, idx))
    return hits


def private_term_report(docs: list[Path], path: Path) -> list[str]:
    terms = load_terms(path)
    return [
        f"{doc.relative_to(REPO_ROOT)}:{line} term #{idx}"
        for doc in docs
        for line, idx in term_hits(doc.read_text(encoding="utf-8"), terms)
    ]


def test_no_fold_wording() -> None:
    hits = [
        f"{doc.relative_to(REPO_ROOT)}:{n}: {line.strip()}"
        for doc in public_docs()
        for n, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1)
        if FOLD.search(line)
    ]
    assert hits == []


def test_no_private_terms() -> None:
    path = terms_file()
    if not path.is_file():
        pytest.skip(f"no private-terms file at $DOTFILES/{TERMS_REL}")
    assert private_term_report(public_docs(), path) == []


def test_term_hits_never_echo_the_term() -> None:
    text = "fine\nsee Acme-Corp here\nacmecorp is not a hit\n"
    assert term_hits(text, ["other", "acme-corp"]) == [(2, 2)]
