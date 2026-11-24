---
name: Hook I/O discipline
description: Gotchas when writing Claude Code hooks (PreCompact, SessionStart, PostToolUse, etc.) + hook config changes (confirm no errors; live on the next tool call)
paths:
  - "**/hooks/*.py"
  - "**/hooks/*.sh"
  - "**/.claude/settings.json"
  - "**/.claude/settings.local.json"
---

# Hook I/O Rules

## Hook config changes

After any hook config change, ask the user to confirm no errors appeared — hook error annotations are NOT included in tool results. Hook config IS hot-reloaded: a hook added mid-session fires on the very next tool call — expect a new blocking hook to gate your own next command.

## Bounded reads on transcript/session files

Hooks that parse transcripts run at the *worst-case* context size (PreCompact fires at 83–89% context; a transcript at that point is commonly 10–50 MB). Never use `fh.readlines()[-N:]`, `str(path.read_text()).splitlines()[-N:]`, or similar — they load the full file before slicing.

Use `collections.deque(fh, maxlen=N)` for tail-N lines, or `fh.seek(-window, 2)` + line-boundary fixup for byte-window reads. Keep peak memory at `N × avg_line_size`, not `file_size`.

## Fail-open wrapper is non-optional

Any hook that can block compaction, session start, or tool use needs `try: main(); except Exception: pass; sys.exit(0)` as the outermost wrapper. One uncaught exception during compaction compounds the very failure the hook exists to cushion.

## Sanitize stdin-derived path components

Filenames/dirs built from `payload["session_id"]` or other stdin fields must be regex-filtered to `[A-Za-z0-9_.-]` (UUIDs pass through). Plans that enumerate failure modes for disk/permission/crash often miss the malformed-input class.

## Hook stdout is not neutral

Each hook type routes stdout differently:
- **`UserPromptSubmit`** — stdout is appended to the user prompt context. A stray `print()` during development ends up in the next turn's prompt and the model responds to it.
- **`SessionStart`** — stdout renders as a system notice at session boot. Intended channel for health warnings (see `session-start-health.py`).
- **`PostToolUse`** — plain stdout goes to the Ctrl-R user transcript ONLY; Claude never sees it. To inject context back to Claude, emit a JSON envelope: `{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext": "<msg>"}}` on stdout (exit 0). See `ruff-check.sh` / `pyright-check.sh` / `impag-budget-check.py` for working examples.
- **`PreToolUse`** — to ALLOW the call while feeding advisory text to Claude, emit `{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext": "<msg>"}}` on stdout (exit 0); `additionalContext` is injected on the next request (verified against the hooks docs, 2026-06-26). Bare stdout is shown to the user, not Claude. `permissionDecisionReason` reaches the model only on `deny`, not `allow` — use `additionalContext` for allows. Exit 2 blocks (stderr → Claude). See `docs-bloat-gate.py` (S2/S3 advisory).
- **`PreCompact`** — stdout is captured by the harness for its own processing; not visible in-band.

**`permissions.deny` `Read(<dir>/**)` also denies Bash `ls`/`cat` and explicit-path Grep there** — to keep a dir out of default search, list it in a ripgrep `.ignore` instead.

Telemetry hooks (log-and-return) MUST exit with empty stdout. Informational hooks on PostToolUse MUST use the JSON envelope, not bare `print()` — a bare `print()` is silently swallowed on PostToolUse, catastrophic on UserPromptSubmit.

---

**Writing or shipping a PreToolUse *blocking* hook (a Bash write-gate)?** → read
`~/.claude/references/hooks-deep-dives.md` for: the write-vs-read regex (avoid heredoc/commit-message
self-blocks), the whole-compound-command block behavior, the ship-a-blocking-hook deliverable checklist
(block+allow demo, README playbook, user-surface pointer), and the write-gate coverage gaps (brace-default
expansions, `source`/`.`/`eval` pipe-to-shell, the bats exec-bit test assumption).
