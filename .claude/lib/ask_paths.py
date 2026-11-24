"""`Edit(...)` ask globs from settings.json as path matchers — shared by destructive-bash-gate D4 and tests."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

EDIT_RULE = re.compile(r"Edit\((.+)\)\Z")


def glob_regex(glob: str) -> re.Pattern[str]:
    """Gitignore-style glob (`**/`, `**`, `*`, `?`) → anchored regex over a base-relative path."""
    out, i = [], 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif glob.startswith("**", i):
            out.append(".*")
            i += 2
        elif glob[i] == "*":
            out.append("[^/]*")
            i += 1
        elif glob[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def edit_ask_globs(settings_path: Path) -> list[str]:
    """The `Edit(<glob>)` entries of permissions.ask; a missing/unparseable file yields []."""
    try:
        rules = json.loads(settings_path.read_text())["permissions"]["ask"]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    return [
        m.group(1) for r in rules if isinstance(r, str) and (m := EDIT_RULE.match(r))
    ]


def _split(glob: str, cwd: str, home: str, settings_dir: str) -> tuple[str, str]:
    """Claude Code rule anchors: `//` absolute, `~/` home, `/` settings dir, else cwd."""
    if glob.startswith("//"):
        return "/", glob[2:]
    if glob.startswith("~/"):
        return home, glob[2:]
    if glob.startswith("/"):
        return settings_dir, glob[1:]
    return cwd, glob.removeprefix("./")


def matching_glob(
    path: str, globs: list[str], cwd: str, home: str, settings_dir: str
) -> str | None:
    """First glob matching absolute `path`, or None."""
    for glob in globs:
        base, rest = _split(glob, cwd, home, settings_dir)
        base = os.path.normpath(base)
        if path != base and not path.startswith(base.rstrip("/") + "/"):
            continue
        rel = os.path.relpath(path, base)
        if glob_regex(rest).match(rel):
            return glob
    return None
