"""README.md hub layout: the nav line leads with System · Why · Catalog · Adopt,
and every nav / "Start here" target resolves (file exists, `#anchor` matches a
GitHub-slugged README heading)."""

from __future__ import annotations

import importlib.util
import re
import sys

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
