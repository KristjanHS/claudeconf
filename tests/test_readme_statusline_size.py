"""README's stated line count for statusline.sh matches the script."""

from __future__ import annotations

import re

from conftest import REPO_ROOT


def test_readme_states_statusline_line_count() -> None:
    lines = len((REPO_ROOT / ".claude" / "statusline.sh").read_text().splitlines())
    readme = (REPO_ROOT / "README.md").read_text()
    m = re.search(r"statusline is (\d+) lines of bash", readme)
    assert m, "README no longer states the statusline's line count"
    assert int(m.group(1)) == lines
