#!/usr/bin/env python3
"""PostToolUse hook — /impag context-budget hard-stop checkpoint.

Reads the EXACT context-token count from the transcript tail with zero
dependencies. The last `assistant` turn's `message.usage` carries the token
counts the Anthropic API reported for that turn; summing
`input_tokens + cache_creation_input_tokens + cache_read_input_tokens` is the
real context size. This is the same formula `statusline.sh` uses (it reads
`current_usage` from the harness), so the hook and statusline agree by
construction — same measurement, not just the same 130k mark.

The read is compaction-aware: a post-compact assistant turn reports the reset
context, so this never false-fires the way a file-size proxy does (the .jsonl
retains evicted history while real context resets down). It is also bounded —
only the final 64 KB of the transcript is read, so peak memory is independent
of transcript size.

Primary trigger: Bash `git commit` (the natural /impag task boundary).
Fallback trigger: any other Bash call once the transcript exceeds the
FALLBACK_PROBE_BYTES floor — guards working-tree-only sessions where no commit
ever fires. The fallback writes a per-session sentinel so it emits at most once
per session; the git-commit path is unthrottled.

Emits a single terse reminder only when the count crosses 130k. Below that
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

# Latency floor for the fallback path only — NOT an accuracy device. A session
# whose transcript is smaller than this cannot hold 130k tokens of context, so
# we skip the tail-read entirely to keep PostToolUse latency negligible on every
# non-commit Bash call in small sessions. (130k tokens is many MB of JSONL;
# 400k bytes is a comfortably safe floor.) The git-commit path always reads.
FALLBACK_PROBE_BYTES = 400_000

# The last assistant turn's reported usage is virtually always in the final few
# KB; reading the last 64 KB keeps peak memory independent of transcript size.
_TAIL_CHUNK = 65536


_GIT_COMMIT_RE = re.compile(r"\bgit\b[^|&;]*?\bcommit(?![A-Za-z0-9_-])")


def read_last_turn_context(transcript_path: Path) -> int:
    """Exact context tokens = the last assistant turn's reported usage.

    Reads only the tail of the transcript. Returns 0 if the tail has no
    assistant turn (fresh/empty session) -> hook stays silent. Compaction-aware:
    a post-compact assistant turn reports the reset context, unlike file size.
    """
    try:
        size = transcript_path.stat().st_size
    except OSError:
        return 0
    if size == 0:
        return 0
    with open(transcript_path, "rb") as f:
        if size > _TAIL_CHUNK:
            f.seek(size - _TAIL_CHUNK)
            f.readline()  # discard possibly-partial first line
        tail = f.read().decode("utf-8", errors="replace")
    for line in reversed(tail.splitlines()):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") != "assistant":
            continue
        usage = (obj.get("message") or {}).get("usage")
        if not usage:
            continue
        return (
            usage.get("input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0)
            + usage.get("cache_read_input_tokens", 0)
        )
    return 0


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

    tokens = read_last_turn_context(p)
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
