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
ever fires. The git-commit path always reads; the fallback path is gated by the
byte floor first.

Sub-agent sessions get their own branch (check_subagent): the settings.json
matcher is `*`, and when the payload carries `agent_id` the hook measures the
agent's OWN transcript under <sid>/subagents/ on ANY tool call — Read/Grep-heavy
research agents are the ones that actually overrun. Main sessions stay Bash-only
via the tool_name guard below.

Emits four graduated bands as context grows: three mild FYI heads-ups at
~80k/100k/115k, then the 130k hard-stop WRAP-UP reminder. The soft bands lead
with the keep-going instruction and keep the token count a de-emphasized trailing
parenthetical with NO "/130k" ratio — the ratio-to-ceiling itself reads as
"almost at the wall". They never make the *budget number* a reason to wrap up
(code review + finish belong to the 130k stop; /retro does NOT — SKILL step 9
defers it to the next chained session via a `retro owed:` marker); finishing early because
the task is genuinely done is always fine — the bands only guard against stopping
on the count alone. Rationale (two real incidents): a manual "only 25k left"
warning once made an agent wrap up at 120k and skip code review; and on this
hook's own first live run the earlier "~Nk of 130k" phrasing still read as a wall
at ~122k — hence the demoted count and the "not on the number alone" wording.

Dedup via a per-session "highwater" sentinel — same `.impag-budget-fired-<sid>`
filename, now storing an integer = the highest band-threshold already emitted.
Each soft band fires once; the hard band keeps nagging on every commit past 130k.
If the measured count drops ≥20k below the highwater (only a compaction/rewind
can do that — a same-session climb only grows), the highwater resets to 0 so the
bands re-arm for the fresh runway.

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

# Graduated budget bands, ascending. `kind`: soft = informational FYI (fires
# once each via the highwater sentinel); hard = the 130k WRAP-UP stop (re-nags on
# every commit). `{t}` renders the ACTUAL token count (tokens // 1000), so the
# fraction shown is real, not the band label. The soft wording is intentionally
# non-stop-flavored and never names an end gate to run now — see the module
# docstring for the incident that shaped it.
BANDS: tuple[tuple[int, str, str], ...] = (
    (
        80_000,
        "soft",
        "[impag-budget] Budget FYI, not a checkpoint — keep going, no action. (~{t}k)",
    ),
    (
        100_000,
        "soft",
        "[impag-budget] Budget FYI, not a checkpoint — keep going normally. (~{t}k)",
    ),
    (
        115_000,
        "soft",
        "[impag-budget] Budget FYI, not a stop — don't wrap up on the number alone. "
        "Keep going if work remains; 130k is the only budget checkpoint. (~{t}k)",
    ),
    (
        HARD_STOP_TOKENS,
        "hard",
        "[impag-budget] ~{t}k — WRAP UP: do NOT start a new task. Finish in-flight "
        "work, save remaining tasks to project_state.md, then run code review → "
        "finish the branch per SKILL step 8 (skip finishing-a-development-branch "
        "on a permanent dev branch) → record 'retro owed: <items>' in Next action. "
        "Do NOT run /retro at this context (SKILL step 9).",
    ),
)

# A measured drop this far below the recorded highwater can only be a
# compaction/rewind (a same-session climb only grows; bands are ≥15k apart, so
# token jitter never falls 20k). Triggers a highwater reset so the bands re-arm.
COMPACTION_RESET_DROP = 20_000

# Sub-agent bands (see check_subagent). A sub-agent's deliverable is its final
# return message; running into auto-compaction degrades it (one general-purpose
# agent measured at 220k on 2026-07-15 with zero warnings). The hard wording
# tells it to end with a continuation-ready report, not to run end gates it
# doesn't have (/retro, finishing-a-development-branch are main-session moves).
SUBAGENT_BANDS: tuple[tuple[int, str, str], ...] = (
    (
        100_000,
        "soft",
        "[subagent-budget] Budget FYI, not a checkpoint — keep going normally. (~{t}k)",
    ),
    (
        HARD_STOP_TOKENS,
        "hard",
        "[subagent-budget] ~{t}k context — WRAP UP: do NOT start new exploration. "
        "Finish the in-flight step only, then END YOUR TURN with a final report: "
        "findings/results so far, files touched, and exactly what remains, so the "
        "caller can continue in a fresh agent.",
    ),
)

# Past the sub-agent hard stop, re-nag every +15k tokens of further growth (the
# sentinel then stores the token count at the last nag instead of the band
# threshold). Sub-agents rarely `git commit`, so the main path's re-nag-on-commit
# trigger would almost never fire for them.
SUBAGENT_RENAG_TOKENS = 15_000


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


def select_band(
    tokens: int, bands: tuple[tuple[int, str, str], ...] = BANDS
) -> tuple[int, str, str] | None:
    """Highest band whose threshold <= tokens, rendered. None below the first band.

    Returns (threshold, kind, message). Band-skipping is intended: a turn jumping
    70k -> 120k selects band 3 (115k), never a backlog of the lower bands.
    """
    selected: tuple[int, str, str] | None = None
    for threshold, kind, template in bands:
        if tokens >= threshold:
            selected = (threshold, kind, template)
        else:
            break
    if selected is None:
        return None
    threshold, kind, template = selected
    return threshold, kind, template.format(t=tokens // 1000)


def read_highwater(sentinel: Path) -> int:
    """Highest band-threshold already emitted this session (0 if none/unreadable).

    The pre-soft-band format was an empty touch-file; int("") raises ValueError
    and we fall back to 0, which safely re-arms rather than silencing a band.
    """
    try:
        return int(sentinel.read_text().strip())
    except (OSError, ValueError):
        return 0


def write_highwater(sentinel: Path, value: int) -> None:
    try:
        sentinel.write_text(str(value))
    except OSError:
        pass


def check_subagent(payload: dict) -> None:
    """Sub-agent branch: measure the AGENT's own transcript, not the parent's.

    Verified empirically 2026-07-15: PostToolUse hooks DO fire inside sub-agents,
    and the payload then carries `agent_id`/`agent_type` — but `transcript_path`
    is the PARENT session's jsonl. The agent's own transcript lives at
    `<parent-dir>/<session_id>/subagents/agent-<agent_id>.jsonl` (layout →
    references/claude-code-persistence.md), with the same assistant-usage
    records, so the tail-read works unchanged.

    Fires on ANY tool call (the settings.json matcher is `*` so Read/Grep-heavy
    research agents — the ones that actually blow up — are covered); the
    byte-floor gate keeps per-call latency negligible below band range.
    """
    parent = Path(payload.get("transcript_path", ""))
    raw_sid = payload.get("session_id") or parent.stem
    sid = re.sub(r"[^A-Za-z0-9_.-]", "_", str(raw_sid))[:80] or "unknown"
    agent_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(payload.get("agent_id")))[:80]
    p = parent.parent / sid / "subagents" / f"agent-{agent_id}.jsonl"
    try:
        if p.stat().st_size < FALLBACK_PROBE_BYTES:
            return
    except OSError:
        return

    tokens = read_last_turn_context(p)
    band = select_band(tokens, SUBAGENT_BANDS)
    if band is None:
        return
    threshold, kind, msg = band

    sentinel = p.parent / f".impag-budget-fired-agent-{agent_id}"
    highwater = read_highwater(sentinel)
    if highwater - tokens >= COMPACTION_RESET_DROP:
        highwater = 0

    # Soft band fires once (sentinel stores its threshold). The hard band fires
    # on first crossing and then re-nags each further SUBAGENT_RENAG_TOKENS of
    # growth — for hard fires the sentinel stores the token count at the nag.
    if threshold > highwater:
        new_highwater = threshold if kind == "soft" else tokens
    elif kind == "hard" and tokens >= highwater + SUBAGENT_RENAG_TOKENS:
        new_highwater = tokens
    else:
        return

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": msg,
                }
            }
        )
    )
    write_highwater(sentinel, max(highwater, new_highwater))


def main() -> None:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return

    if payload.get("agent_id"):
        check_subagent(payload)
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

    # Fallback path (any non-commit Bash): byte-proxy latency gate first — a
    # transcript below the floor cannot hold even the earliest (80k) band, so
    # skip the tail-read on every Bash call in small sessions. The git-commit
    # path always reads.
    if not is_commit:
        try:
            if p.stat().st_size < FALLBACK_PROBE_BYTES:
                return
        except OSError:
            return

    tokens = read_last_turn_context(p)
    band = select_band(tokens)
    if band is None:
        return
    threshold, kind, msg = band

    # Per-session highwater sentinel (integer = highest threshold already
    # emitted). Sanitize the stdin-derived session id before using it in a
    # filename so a malformed value can't escape the transcript directory.
    raw_sid = payload.get("session_id") or p.stem.split(".")[0]
    session_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(raw_sid))[:80] or "unknown"
    sentinel = p.parent / f".impag-budget-fired-{session_id}"
    highwater = read_highwater(sentinel)

    # Compaction re-arm: a measured count this far below the recorded highwater
    # means the context was reset, so re-warn from the bottom.
    if highwater - tokens >= COMPACTION_RESET_DROP:
        highwater = 0

    # Emit a band iff it hasn't been emitted yet (threshold > highwater), OR it's
    # the hard stop on a commit — the 130k WRAP-UP re-nags on every commit past
    # the wall, exactly as before, while soft bands fire once each.
    if not (threshold > highwater or (kind == "hard" and is_commit)):
        return

    # PostToolUse plain stdout goes to the Ctrl-R transcript only — it is NOT
    # injected into Claude's context. Emit the documented JSON envelope so
    # `additionalContext` is fed back as tool-result context.
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": msg,
                }
            }
        )
    )

    new_highwater = max(highwater, threshold)
    if new_highwater != highwater:
        write_highwater(sentinel, new_highwater)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Fail-open: never block a commit.
        pass
    sys.exit(0)
