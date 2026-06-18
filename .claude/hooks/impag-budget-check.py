#!/usr/bin/env python3
"""PostToolUse hook — /impag context-budget hard-stop checkpoint (PORTABLE).

This is the self-contained variant of the author's budget governor. The
original imports `token_monitor.parser.parse_last_turn` from a private,
editable-installed package that is NOT on PyPI — copied as-is it raises
ModuleNotFoundError on anyone else's machine. This version drops that import
and estimates the token count from the transcript file size (`bytes / 4`),
the same cheap proxy the fallback path already uses. Zero dependencies, but
note two real inaccuracies measured against an actual parser:
  * On a LIVE session bytes/4 runs ~1.4-1.8x high — JSONL structure, escaping,
    and tool envelopes push bytes-per-token well above the prose ~4. So this
    hook trips conservatively EARLY (real context ~85-95k when bytes/4 hits
    130k), which is acceptable for a "wrap up before the cliff" governor.
  * After a COMPACTION it runs 2.4-3.9x high and KEEPS CLIMBING: the .jsonl
    retains evicted history while the real context resets down. In a long,
    compacted session this WILL fire spuriously. A real parser
    (parse_last_turn().total_context) is compaction-aware and avoids this.
To upgrade to exact, compaction-aware accounting, reinstate a real token count
in `estimate_tokens` (e.g. your own tokenizer) and keep everything else.

Primary trigger: Bash `git commit` (the natural /impag task boundary).
Fallback trigger: any other Bash call once the transcript size proxy exceeds
the FALLBACK_PROBE_BYTES floor — guards working-tree-only sessions where no
commit ever fires. The fallback writes a per-session sentinel so it emits at
most once per session; the git-commit path is unthrottled.

Emits a single terse reminder only when the estimate crosses 130k. Below that
band the hook is silent; the statusline turns yellow at the same 130k mark, so
there is no soft-band signal before hard-stop by design.

Fail-open: any failure (unreadable transcript, stat error) exits 0 so commits
are never blocked.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# 130k is the /impag wrap-up threshold. Aligned with the statusline 130k yellow
# mark, leaving ~70k headroom before the 200k session-stop budget so review +
# finish-branch + /retro can run with a clean-enough transcript.
HARD_STOP_TOKENS = 130_000

# Cheap byte-proxy gate for the fallback path. Because bytes/4 runs ~1.5x high
# on live sessions (see module docstring), 400k bytes is well under the 130k
# hard-stop — a safe floor below which we skip even the stat-based estimate to
# keep PostToolUse latency negligible on small sessions.
FALLBACK_PROBE_BYTES = 400_000

# Portable token estimate: ~4 bytes per token. Same proxy as the fallback gate,
# now reused as the actual measure (no private token_monitor dependency).
BYTES_PER_TOKEN = 4


_GIT_COMMIT_RE = re.compile(r"\bgit\b[^|&;]*?\bcommit(?![A-Za-z0-9_-])")


def estimate_tokens(transcript_path: Path) -> int:
    """Estimate context tokens from transcript byte size (portable proxy)."""
    return transcript_path.stat().st_size // BYTES_PER_TOKEN


def is_git_commit(tool_name: str, tool_input: dict) -> bool:
    if tool_name != "Bash":
        return False
    cmd = str(tool_input.get("command", ""))
    # Match `git commit` (incl. `git -C /path commit`, `git -c x=y commit`)
    # while rejecting identifier-continuation neighbours: `git commit-tree`,
    # `git config core.commitGraph`, `commitish`, etc. — via the negative
    # lookahead. `[^|&;]*?` keeps the prefix from straddling a piped boundary.
    # `git commit --help` is rejected by the trailing substring guard.
    if not _GIT_COMMIT_RE.search(cmd):
        return False
    return "--help" not in cmd


def format_message(tokens: int) -> str | None:
    if tokens >= HARD_STOP_TOKENS:
        return (
            f"[impag-budget] ~{tokens // 1000}k — WRAP UP: do NOT start a new "
            f"task. Finish in-flight work, save remaining tasks to "
            f"memory/project_state.md, then run code review → "
            f"finishing-a-development-branch → /retro."
        )
    return None


def main() -> None:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return

    tool_name = payload.get("tool_name", "")
    if tool_name != "Bash":
        return
    tool_input = payload.get("tool_input") or {}

    transcript_path = payload.get("transcript_path", "")
    if not transcript_path:
        return
    p = Path(transcript_path)
    if not p.is_file():
        return

    is_commit = is_git_commit(tool_name, tool_input)
    sentinel: Path | None = None
    if not is_commit:
        # Fallback path: byte-proxy gate first (avoid stat noise on every Bash
        # call in small sessions), then per-session dedup so we don't inject the
        # same reminder repeatedly once we're past 130k.
        try:
            if p.stat().st_size < FALLBACK_PROBE_BYTES:
                return
        except OSError:
            return
        raw_sid = payload.get("session_id") or p.stem.split(".")[0]
        # Sanitize before using in a filename: stdin-derived values must be
        # constrained to a safe charset so a malformed session_id can't escape
        # the transcript directory (path traversal / unexpected write target).
        session_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(raw_sid))[:80] or "unknown"
        sentinel = p.parent / f".impag-budget-fired-{session_id}"
        if sentinel.exists():
            return

    tokens = estimate_tokens(p)
    if tokens < HARD_STOP_TOKENS:
        return

    # tokens >= HARD_STOP_TOKENS is guaranteed above, so format_message returns
    # a non-None reminder here. Emit and (on the fallback path) record the
    # per-session sentinel together.
    msg = format_message(tokens)
    assert msg is not None
    # PostToolUse plain stdout goes to the Ctrl-R transcript only — it is NOT
    # injected into Claude's context. Emit the documented JSON envelope so
    # `additionalContext` is fed back as tool-result context.
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": msg,
        }
    }))
    if sentinel is not None:
        try:
            sentinel.touch()
        except OSError:
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Fail-open: never block a commit.
        pass
    sys.exit(0)
