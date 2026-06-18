#!/usr/bin/env python3
"""SessionStart(startup) hook — session-boot health check.

Why it saves context:
  (a) Warns if any MEMORY.md under ~/.claude/projects/*/memory/ exceeds 180
      lines. Claude Code silently drops memory content past ~200 lines, so the
      warning lands 20 lines early — giving you room to graduate entries to a
      reference before they vanish from context unnoticed.
  (b) Garbage-collects stale `.impag-budget-fired-<session_id>` sentinels
      (older than 30 days). The budget hook (impag-budget-check.py) drops one
      sentinel per session for fallback dedup; sessions end but sentinels
      accumulate forever. A single sweep here keeps the budget hook's hot path
      fast and concentrates lifecycle logic in one place.

Fail-open: any failure exits 0 so session startup is never blocked.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

MEMORY_WARN_LINES = 180
PROJECTS_DIR = Path.home() / ".claude" / "projects"
BUDGET_SENTINEL_MAX_AGE_DAYS = 30


def count_lines(path: Path) -> int:
    try:
        with path.open("rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def find_oversized_memory_files() -> list[tuple[Path, int]]:
    if not PROJECTS_DIR.is_dir():
        return []
    oversized: list[tuple[Path, int]] = []
    for mem_file in PROJECTS_DIR.glob("*/memory/MEMORY.md"):
        n = count_lines(mem_file)
        if n > MEMORY_WARN_LINES:
            oversized.append((mem_file, n))
    return oversized


def prune_stale_budget_sentinels(now: float | None = None) -> int:
    """Unlink `.impag-budget-fired-<sid>` files older than 30 days.

    Called silently at session start. The budget hook drops one sentinel per
    session and never cleans up; without a sweep here, they accumulate forever.
    Returns the count pruned for testing; production callers ignore it.
    """
    if not PROJECTS_DIR.is_dir():
        return 0
    cutoff = (now if now is not None else time.time()) - BUDGET_SENTINEL_MAX_AGE_DAYS * 86400
    pruned = 0
    for sentinel in PROJECTS_DIR.glob("*/.impag-budget-fired-*"):
        try:
            if sentinel.stat().st_mtime < cutoff:
                sentinel.unlink()
                pruned += 1
        except OSError:
            continue
    return pruned


def main() -> None:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    source = payload.get("source", "")
    if source and source != "startup":
        return

    # Silent housekeeping: drop budget-hook sentinels that outlived their
    # session by 30+ days. No stdout — the user doesn't need to see it.
    try:
        prune_stale_budget_sentinels()
    except Exception:
        pass

    messages: list[str] = []

    for path, n_lines in find_oversized_memory_files():
        try:
            rel = path.relative_to(Path.home())
            display = f"~/{rel}"
        except ValueError:
            display = str(path)
        messages.append(
            f"!  MEMORY.md {display} = {n_lines} lines "
            f"(>{MEMORY_WARN_LINES}; silent-drop at ~200 — graduate entries)"
        )

    if messages:
        print("\n".join(messages))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
