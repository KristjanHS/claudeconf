#!/usr/bin/env python3
"""SessionStart(startup) hook — session-boot health check.

Sub-checks from a private design note #19:
  (a) Warn if any MEMORY.md under ~/.claude/projects/*/memory/ exceeds 180 lines.
      Silent-drop threshold is ~200 (issue #39811); we warn 20 lines early so
      there's room to graduate content before drops start.
  (d) Host only (no /.dockerenv): warn when CLAUDE_SAFE is unset — claude launched past
      claude-safe (venv/brew bin, absolute path). Undetected: a nested launch inheriting CLAUDE_SAFE=1.
  (e) REMOVED 2026-07-25 — the project_state.md size band. Every fire opened a
      relocate/compress pass whose only output was moved prose, so the band and
      all other size caps were retired; admission discipline replaced them
      (~/.claude/references/memory-system.md §No size caps). Check (a) stays
      because ~200 lines is a harness truncation limit, not a style budget.
  (f) Warn when project_state.md grows a `##` section its content test does not
      admit (memory-system.md §Roles table: the ONE armed item + chain/sentinel
      state + active-task user-owed + a roadmap pointer). This is NOT the
      retired band under another name: it measures nothing and a file of any
      length passes while its sections stay admitted. Added 2026-08-01 after a
      52k project_state.md accumulated `## Other open work` (227 lines) and
      `## Live code constraints` (127 lines). The audit found the delete classes
      already forbade both — the gap was that nothing DETECTED the drift, so it
      compounded unnoticed for months. A heading is the earliest visible symptom:
      it appears the moment a writer routes content to the wrong layer.

      ADVISORY, NEVER A TASK. This is the failure mode that retired check (e):
      a session-start warning reads as a work item, the agent opens a shrink
      pass, and the turn's whole output is moved prose. So (f) says outright
      that it is not to be acted on, and fires ONCE per distinct drift state
      (sentinel keyed on the stray-heading set) — a drift it already reported
      stays silent on every later session, so it can never nag a session into
      "fixing" it. It re-fires only when a NEW unadmitted section appears.
      Routing happens at the next write to the file, or in a user-run
      /condense; never as an autonomous response to this line.

Sub-check (b) from the plan (enabledPlugins vs loaded-plugins diff) was dropped
during design — no stable way to enumerate loaded plugins from a hook without
parsing internal state, and the mismatch is rare.
Sub-check (c) (autocompact-override notice) was dropped 2026-04-24 after the
window moved to 1M: the 75% override now lands at 750k, well past the user's
300k session-stop budget, so the notice was factually misleading.

Side effect (Fix 2.3 from a private design note):
  Garbage-collect `.impag-budget-fired-<session_id>` sentinels older than
  30 days. The /impag budget hook (impag-budget-check.py) writes one per
  session for fallback dedup; sessions end, sentinels accumulate
  indefinitely. Single sweep at session start keeps the budget hook's hot
  path fast and concentrates lifecycle logic here.

Fail-open: any failure exits 0 so session startup is never blocked.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

MEMORY_WARN_LINES = 180
PROJECTS_DIR = Path.home() / ".claude" / "projects"
BUDGET_SENTINEL_MAX_AGE_DAYS = 30
DOCKERENV = Path("/.dockerenv")

# Check (f). A `##` heading in project_state.md whose text matches none of these
# is content the Roles table routes to another layer (roadmap menus, §OWED[USER],
# a domain reference, the plan doc). Kept deliberately permissive — the point is
# to catch a NEW state-holding section, not to police wording.
STATE_SECTION_OK = re.compile(
    r"next action|chain|status|sentinel|pointer|owed|user-owed",
    re.IGNORECASE,
)
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")


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


def find_unadmitted_state_sections() -> list[tuple[Path, list[str]]]:
    """Check (f): project_state.md `##` sections its content test does not admit.

    Reads headings only — no size, no line count, no byte total is computed or
    compared anywhere in this function, deliberately (§No size caps). A file is
    flagged for holding the WRONG KIND of content, never for holding a lot of it.

    Reports each distinct drift state ONCE. A `.project-state-drift-<digest>`
    sentinel beside the memory dir records the stray-heading set already
    surfaced; an unchanged set stays silent forever after. Without this the
    warning repeats every session and eventually pressures some session into an
    unasked-for shrink pass — the exact cost that retired the size band.
    """
    if not PROJECTS_DIR.is_dir():
        return []
    flagged: list[tuple[Path, list[str]]] = []
    for state_file in PROJECTS_DIR.glob("*/memory/project_state.md"):
        try:
            text = state_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        strays = [
            m.group(1)
            for line in text.splitlines()
            if (m := HEADING_RE.match(line)) and not STATE_SECTION_OK.search(m.group(1))
        ]
        if not strays:
            continue
        digest = hashlib.sha256("\n".join(sorted(strays)).encode("utf-8")).hexdigest()[
            :12
        ]
        sentinel = state_file.parent.parent / f".project-state-drift-{digest}"
        try:
            if sentinel.exists():
                continue  # already surfaced — never re-nag an unchanged drift
            sentinel.touch()
        except OSError:
            pass  # fail-open: a sentinel we cannot write just means we report again
        flagged.append((state_file, strays))
    return flagged


def prune_stale_budget_sentinels(now: float | None = None) -> int:
    """Unlink `.impag-budget-fired-<sid>` files older than 30 days.

    Called silently at session start. The budget hook drops one sentinel per
    session and never cleans up; without a sweep here, they accumulate forever
    (15+ already on disk across projects on this host). Returns the count
    pruned for testing; production callers don't surface the number.
    """
    if not PROJECTS_DIR.is_dir():
        return 0
    cutoff = (
        now if now is not None else time.time()
    ) - BUDGET_SENTINEL_MAX_AGE_DAYS * 86400
    pruned = 0
    # Two sentinel locations: main sessions drop them at the slug top level;
    # sub-agent runs drop them next to the agent transcript under
    # <slug>/<sid>/subagents/ (see impag-budget-check.check_subagent).
    sentinels = list(PROJECTS_DIR.glob("*/.impag-budget-fired-*"))
    sentinels += PROJECTS_DIR.glob("*/*/subagents/.impag-budget-fired-*")
    for sentinel in sentinels:
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

    if os.environ.get("CLAUDE_SAFE") != "1" and not DOCKERENV.exists():
        messages.append(
            "⚠  claude started without the claude-safe wrapper (CLAUDE_SAFE unset): "
            "trust + hash gates skipped. Relaunch via ~/bin/claude; check `type -a claude`."
        )

    for path, n_lines in find_oversized_memory_files():
        try:
            rel = path.relative_to(Path.home())
            display = f"~/{rel}"
        except ValueError:
            display = str(path)
        messages.append(
            f"⚠  MEMORY.md {display} = {n_lines} lines "
            f"(>{MEMORY_WARN_LINES}; silent-drop at ~200 — graduate entries)"
        )

    for path, strays in find_unadmitted_state_sections():
        try:
            display = f"~/{path.relative_to(Path.home())}"
        except ValueError:
            display = str(path)
        named = ", ".join(f"'{s}'" for s in strays[:3])
        more = f" (+{len(strays) - 3} more)" if len(strays) > 3 else ""
        messages.append(
            f"ℹ  FYI, no action now: project_state.md {display} holds section(s) "
            f"its content test does not admit ({named}{more}). Route them at the "
            f"NEXT write to that file, or leave it for a user-run /condense. Do "
            f"NOT open a shrink/relocate pass for this — it is not a task, not a "
            f"blocker, and this notice will not repeat."
        )

    if messages:
        print("\n".join(messages))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
