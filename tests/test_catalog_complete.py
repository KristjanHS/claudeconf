"""docs/catalog.md names every hook, rule, reference and skill in .claude/."""

from __future__ import annotations

import re

import pytest

from conftest import REPO_ROOT

CLAUDE = REPO_ROOT / ".claude"


def pieces() -> list[str]:
    hooks = [p.name for p in (CLAUDE / "hooks").iterdir() if p.suffix in {".py", ".sh"}]
    rules = [p.name for p in (CLAUDE / "rules").glob("*.md")]
    refs = [p.name for p in (CLAUDE / "references").glob("*.md")]
    skills = [
        p.name for p in (CLAUDE / "skills").iterdir() if (p / "SKILL.md").is_file()
    ]
    return sorted({*hooks, *rules, *refs, *skills, "statusline.sh"})


@pytest.mark.parametrize("name", pieces())
def test_catalog_names_piece(name: str) -> None:
    catalog = (REPO_ROOT / "docs" / "catalog.md").read_text()
    row = rf"^(\| `{re.escape(name)}` \||- `{re.escape(name)}`)"
    assert re.search(row, catalog, re.M), f"docs/catalog.md has no row for `{name}`"


def test_inventory_is_nonempty() -> None:
    names = pieces()
    assert len(names) > 40 and "impag" in names and "docs-bloat-gate.py" in names
