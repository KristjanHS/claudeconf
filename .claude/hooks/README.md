# Claude Code runtime hooks

Claude Code runs these scripts at lifecycle events; `.claude/settings.json` wires them up. To use one,
copy it into `~/.claude/hooks/` and merge its `settings.json` block by hand. (The `hooks/` at the repo
root is something else: git hooks.)

Python hooks exit 0 on an internal error, so a hook bug never blocks compaction, session start or a tool
call. The one exception is the destructive gate, which blocks a command it can't parse if it looks
dangerous.

## The hooks

| File | Event (matcher) | What it does |
|---|---|---|
| `pre-compact.py` | `PreCompact` | Copies the transcript to `~/.claude/projects/<cwd-slug>/snapshots/` before compaction, with the active plan, task and todos in `sidecar.json` |
| `post-compact-restore.py` | `SessionStart` (`compact\|resume`) | Prints where the newest snapshot is and which plan and task were active |
| `docs-bloat-gate.py` | `PreToolUse` (`Write\|Edit\|Bash`) | Nudges on bloated `.md` writes, blocks growth of capped files; [section below](#docs-bloat-gatepy) |
| `impag-budget-check.py` | `PostToolUse` (`Bash`) | Tells a long `/impag` run when to wrap up; [section below](#impag-budget-checkpy) |
| `destructive-bash-gate.py` | `PreToolUse` (`Bash`) | Blocks destructive commands that deny rules miss; [section below](#destructive-bash-gatepy) |
| `external-process-test-gate.py` | `PreToolUse` (`Write\|Edit`) | Keeps docker, browser and HTTP tests in `tests/manual/`; [section below](#external-process-test-gatepy) |
| `agent-model-pin-gate.py` | `PreToolUse` (`Agent`) | Blocks an Agent call whose model family differs from the agent's pin; [section below](#agent-model-pin-gatepy) |
| `ruff-check.sh` | `PostToolUse` (`Write\|Edit`, `Bash`), `Stop`, `SubagentStop` | Lint ratchet against the committed baseline; [section below](#ruff-checksh) |

Compaction keeps about 12% of the original tokens, and its summary can drop reasoning a task still needs.
The snapshot is the full copy to go back to.

## Hook specs

### `docs-bloat-gate.py`

Watches `.md` writes. It warns, and lets the write through, on three things: a stock slop phrase in the
added text, an addition over 100 characters with lexical density under 0.45, or a new audit-style file at
the `docs/` root. Each warning fires at most once per session.

It blocks on gated files: `docs/spec.md` and `.claude/rules/*.md` when the project has them, or what
`.claude/docs-bloat-gate.json` lists. An edit that grows one past its cap blocks, and so does any Bash
command that writes to one (use Write or Edit). The cap goes by the file's current length: 150 characters
under 50 lines, 800 under 500, 2000 above. A new file or a new `##` section of up to 30 lines passes.
`<!-- docs-bloat-gate-override: <reason of 30+ chars> -->` lets an edit through unless the reason uses a
word like "fix" or "update"; after three overrides every over-cap edit blocks until the next session.
Memory files are exempt. Slop and density warnings log to `~/.claude/state/docs-bloat-blocks.log`; cap
and audit-doc fires go to `docs/analysis/bloat-overrides.log` when that dir exists, else the same file.

### `impag-budget-check.py`

Its job is to stop a long `/impag` run from taking on new work before the context fills. Checks happen on
every `git commit`, plus any `Bash` call once the transcript is past 400 KB. Each check reads just the
last 64 KB of the transcript and adds up three counts from the last assistant turn: `input_tokens`,
`cache_creation_input_tokens` and `cache_read_input_tokens`. Nothing else is read.

At 120k, 150k and 175k tokens it sends a one-time note that says keep going. At 200k it tells Claude, on
every commit, to start nothing new: finish what's in flight, save the remaining tasks, run code review,
finish the branch and record the retro as owed. A sub-agent gets a note at 150k and a stop at 200k telling
it to end with a report the next agent can continue from, checked only when it runs Bash.

Notes go through the `additionalContext` JSON envelope, because plain `PostToolUse` stdout never reaches
Claude. If the count drops 20k below the session's high, the hook takes it as a compaction and re-arms the
notes. `statusline.sh` sums the same three counts and turns yellow at the same 200k.

### `destructive-bash-gate.py`

`PreToolUse` (`Bash`). Exits 2 on what prefix-match deny rules can't catch: recursive `rm` on `/`, `~`,
`$HOME`, bare-variable roots or top-level system dirs (and any `--no-preserve-root`), a downloader piped or
substituted into a shell, and writes into a `.ssh` dir. Writes into a path an `Edit(...)` ask rule guards
get a prompt instead (needs `~/.claude/lib/ask_paths.py`). It reads tokens, not text, so a commit message
or heredoc that only mentions `rm -rf /` passes. There is no bypass. Run the command yourself, or take the
hook out of `settings.json`. Blocks log to `~/.claude/state/destructive-bash-blocks.log`.

### `external-process-test-gate.py`

`PreToolUse` (`Write|Edit`) on `tests/**/*.py`, except `tests/manual/**`, `tests/__init__.py` and
`tests/conftest.py`. Blocks test code that imports `docker`, `playwright` or `selenium`, calls
`requests.<verb>(`, or launches `docker`, `kubectl`, `playwright` or `selenium` through `subprocess` or
`os.system`. Such tests belong in `tests/manual/`, where the default `pytest` run won't pick them up.
Your project's own toolchain called through `subprocess.run` is fine. Need an exception? Add
`<!-- external-process-test-gate-override: <reason of 10+ chars> -->` to the file; overrides are logged to
`~/.claude/logs/external-process-test-overrides.log`.

### `agent-model-pin-gate.py`

`PreToolUse` (`Agent`). Exits 2 when an Agent call's `model` family (opus, sonnet, haiku or fable, from
an alias or a full ID) differs from the `model:` pin in the subagent's definition. It looks in the
project's `.claude/agents/` first, then `~/.claude/agents/`. There is no bypass. For a cheap read-only run,
use `Explore`, not a downshifted pinned agent. Blocks log to `~/.claude/state/agent-model-pin-blocks.log`.

### `ruff-check.sh`

Runs lint and format checks after `Write|Edit`, lint only after `Bash` (on `.py` files the command left
dirty), and every check again on `Stop`/`SubagentStop`. It blocks only when the count of a lint
`(code, message)` pair grows past the file's committed baseline. Format drift comes back as a note.
Per-edit runs skip codes that show up mid-edit (`F401`, `F821` and the rest of its `skip` list); the
`Stop` pass and any `git commit` check them all. Uses the project's uv-locked `ruff` if there is one, else
the host's. Needs `jq` and `git`. The end-of-turn report fires once: fix the findings, or end the turn
again to keep them.

## Trying a hook in isolation

Each hook reads a JSON event payload on stdin. For the bloat gate:

```sh
echo '{"tool_name":"Write","tool_input":{"file_path":"/tmp/scratch.md","content":"We should leverage this approach."}}' \
  | python3 ~/.claude/hooks/docs-bloat-gate.py
echo "exit code: $?"   # expect exit 0 and a JSON nudge
```

## Automated tests

`python3 -m pytest` runs the suite. `impag-budget-check.py` has `tests/test_impag_budget_check.py`;
`tests/test_security_fixes.py` covers `pre-compact.py`'s input hardening and only the log-path containment
of `docs-bloat-gate.py`.
