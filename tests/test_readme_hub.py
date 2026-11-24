"""README.md hub layout: the nav line leads with System · Why · Catalog · Adopt,
and every nav / "Start here" target resolves (file exists, `#anchor` matches a
GitHub-slugged README heading). docs/*.md (not docs/plans) link back into the hub:
every `README.md#…` they cite resolves, and the system.md / why.md cross-links exist."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from urllib.parse import unquote

import pytest

from conftest import REPO_ROOT

_spec = importlib.util.spec_from_file_location(
    "doc_links", REPO_ROOT / "tests" / "test_doc_links.py"
)
assert _spec is not None and _spec.loader is not None
doc_links = importlib.util.module_from_spec(_spec)
sys.modules["doc_links"] = doc_links
_spec.loader.exec_module(doc_links)

README = REPO_ROOT / "README.md"
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
NAV_LEAD = ["System", "Why", "Catalog", "Adopt"]
NAV_THEN = ["Adoption", "Quick start"]


def nav_links() -> list[tuple[str, str]]:
    """Links on the first prose line made only of ` · `-separated links."""
    for _, line in doc_links.prose_lines(README.read_text(encoding="utf-8")):
        parts = line.strip().split(" · ")
        if len(parts) > 1 and all(LINK.fullmatch(p) for p in parts):
            return [LINK.fullmatch(p).groups() for p in parts]  # type: ignore[union-attr]
    raise AssertionError("README.md has no ` · `-separated nav line")


def start_here_links() -> list[tuple[str, str]]:
    text = README.read_text(encoding="utf-8")
    m = re.search(r"^\*\*Start here\*\*\n(.*?)(?=^\*\*)", text, re.S | re.M)
    assert m, "README.md has no **Start here** group"
    return LINK.findall(m.group(1))


def unresolved(target: str) -> str | None:
    ref, _, frag = target.partition("#")
    if ref:
        dest = REPO_ROOT / ref
        if not dest.exists():
            return f"{target}: missing file"
        if frag and frag not in doc_links.anchors(dest):
            return f"{target}: no such heading in {ref}"
    elif frag not in doc_links.anchors(README):
        return f"{target}: no such README heading"
    return None


def test_nav_leads_with_hub_labels_in_order() -> None:
    labels = [label for label, _ in nav_links()]
    assert labels[: len(NAV_LEAD) + len(NAV_THEN)] == NAV_LEAD + NAV_THEN


@pytest.mark.parametrize("group", ["nav", "start-here"])
def test_hub_targets_resolve(group: str) -> None:
    links = nav_links() if group == "nav" else start_here_links()
    assert links
    assert [p for _, t in links if (p := unresolved(t))] == []


def test_start_here_groups_system_why_adoption() -> None:
    targets = {t for _, t in start_here_links()}
    assert {"docs/system.md", "docs/why.md", "#-adoption"} <= targets


def readme_cites(docs: Path, readme: Path) -> list[tuple[str, str]]:
    """`(doc, #fragment)` for each link into `readme` from `docs/*.md` (top level only,
    so docs/plans is out), skipping fenced blocks and inline code."""
    out: list[tuple[str, str]] = []
    for doc in sorted(docs.glob("*.md")):
        for _, line in doc_links.prose_lines(doc.read_text(encoding="utf-8")):
            line = doc_links.INLINE_CODE.sub("", line)
            for a, b in doc_links.INLINE_LINK.findall(line):
                ref, _, frag = (a or b).partition("#")
                if ref and (doc.parent / unquote(ref)).resolve() == readme.resolve():
                    out.append((doc.name, unquote(frag)))
    return out


def unresolved_cites(docs: Path, readme: Path) -> list[str]:
    heads = doc_links.anchors(readme)
    return [f"{d}: #{f}" for d, f in readme_cites(docs, readme) if f and f not in heads]


def test_docs_readme_anchors_resolve() -> None:
    cites = readme_cites(REPO_ROOT / "docs", README)
    assert any(f for _, f in cites), "no README.md#anchor cited from docs/*.md"
    assert unresolved_cites(REPO_ROOT / "docs", README) == []


@pytest.mark.parametrize(
    ("doc", "frag"),
    [
        ("system.md", "-does-this-actually-work"),
        ("system.md", "-adoption"),
        ("why.md", ""),
    ],
)
def test_docs_link_back_to_hub(doc: str, frag: str) -> None:
    assert (doc, frag) in readme_cites(REPO_ROOT / "docs", README)


def test_why_opens_with_hub_and_system_backlink() -> None:
    text = (REPO_ROOT / "docs" / "why.md").read_text(encoding="utf-8")
    first = next(
        line
        for _, line in doc_links.prose_lines(text)
        if line.strip() and not line.startswith("#")
    )
    targets = [t for _, t in LINK.findall(first)]
    assert targets[:2] == ["../README.md", "system.md"]


def test_planted_readme_cite_breakage_is_reported(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("# Hub\n## 🤝 Adoption\n", encoding="utf-8")
    docs = tmp_path / "docs"
    (docs / "plans").mkdir(parents=True)
    (docs / "a.md").write_text(
        "[ok](../README.md#-adoption) [ok](../README.md) [bad](../README.md#-gone)\n"
        "`[ignored](../README.md#-in-code)`\n"
        "```\n[ignored](../README.md#-in-fence)\n```\n",
        encoding="utf-8",
    )
    (docs / "plans" / "p.md").write_text(
        "[x](../../README.md#-plan-only)\n", encoding="utf-8"
    )
    assert unresolved_cites(docs, readme) == ["a.md: #-gone"]
