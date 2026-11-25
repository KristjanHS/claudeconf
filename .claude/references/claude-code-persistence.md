# Claude Code On-Disk Persistence Layout

For hook code, forensic tooling, or any script that reads/writes under `~/.claude/projects/`. Pulled on entry
from `~/.claude/rules/claude-code-persistence.md`. Verified empirically 2026-04-19.

## Layout per project

```
~/.claude/projects/<cwd-slug>/
  <session-id>.jsonl              # full transcript, append-only
  <session-id>/
    subagents/
      agent-<id>.jsonl            # full sub-agent transcript (mode 600)
      agent-<id>.meta.json        # ~80 byte sidecar
    tool-results/
      toolu_<id>.txt              # large tool outputs offloaded out of jsonl
  snapshots/                      # PreCompact hook output (insurance only)
    <ISO-ts>-<sid>/
      transcript.jsonl
      sidecar.json
  memory/
    MEMORY.md                     # auto-memory index
    <name>.md                     # individual memory files
```

`<cwd-slug>` = `re.sub(r"[^a-zA-Z0-9]", "-", str(cwd))` (the binary's `replace(/[^a-zA-Z0-9]/g,"-")`, read 2026-10-13; `/` and `.` are only the common cases — `_`, `+`, `@`, spaces map too). So `~/projects/dotfiles` →
`-home-kristjans-projects-dotfiles`, and a `claude --worktree` cwd `…/.claude/worktrees/wt` → `…--claude-worktrees-wt`.

## Load-bearing facts

- **`<sid>.jsonl` is append-only.** Verified by SHA-256 of head-N lines staying stable across N+12 added turns.
  Don't write per-turn snapshot hooks "just in case" — disk is already the per-turn record.
- **Compaction = append, not rewrite.** Pre-compact turns are preserved on disk; the compact summary lands as
  a new `user`-type message with `"isCompactSummary":true`. Sample: 417-line session with summary at line 401
  = 401 pre-compact turns intact.
- **`isCompactSummary:true` is the canonical compaction marker.** Use this for forensic detection, not the
  `PostCompact` hook payload field name (which has variants `compaction_summary` vs `compact_summary` across
  versions).
- **Tool results are offloaded above some size threshold** to `<sid>/tool-results/toolu_<id>.txt`. JSONL inline
  content is then a pointer (`sourceToolUseID`). Forensics that only parse JSONL inline miss these — must walk
  the dir.
- **`message.usage` is copied onto every content-block record.** One JSONL record is written per content
  block (`thinking`, `text`, each `tool_use`), and each carries a *full copy* of the same `usage` object.
  Measured: 173 assistant records = 51 real API calls. Any script summing `usage` per record inflates calls
  and tokens ~3.4×. **Dedupe by `requestId`** (fall back to `message.id`). The content blocks themselves are
  *split* across those records, not duplicated — summing block content is safe. The ~3.4× is an *average*,
  not a constant: the factor = records-per-turn, so a heavily tool-batched turn inflates far more (measured
  5.2× on a session with a 13-tool-call turn). Per-record `output_tokens` sums therefore rank *well-batched*
  sessions as false output "outliers" — dedupe before comparing sessions, or good batching looks like waste.
- **`thinking` blocks persist with an empty `thinking` field** (only `signature` survives — 1,175 blocks,
  0 chars). Reasoning is ~73% of reported `output_tokens` and is invisible on disk; never estimate output
  cost from transcript text. Cost model → `~/projects/dotfiles/docs/research_results/context-cost-model.md`.
- **Sub-agent transcripts live in `<sid>/subagents/`**, NOT in the parent JSONL. Decisions made inside
  `Agent(...)` dispatches are invisible to anything that only reads parent JSONL. Walk siblings to recover
  them.
- **`/rewind` leaves no native JSONL marker.** Field-scan across all JSONLs returned zero rewind-native field
  names. Forensics that diff sessions need a heuristic (parentUuid chain breaks, abrupt timestamp gaps) to
  detect rewinds — exclude affected ranges from continuation-quality metrics.
- **The 9-section compact prompt has no section for reasoning chains.** §5 "Problem Solving" captures decision
  *outcomes*; §9 "Context for Continuing Work" carries forward state. Deliberation paths are dropped by
  design — primary forensic target for "lost reasoning" detection.
- **The transcript is keyed by session id, not mtime.** `<sid>.jsonl` where `<sid>` is the session UUID (same
  UUID as the scratchpad dir). `ls -t *.jsonl | head -1` picks a *different, more recently touched* session and
  silently returns zero hits — locate by `grep -rl "<known-string>"` instead.
- **Role provenance settles "did the harness say that, or did I?"** Genuine background-task completions are
  `role='user'` messages carrying a `<task-notification>` block with `<status>` + exit code. A
  `"Background task <id> completed"` string sitting in a `role='assistant'` message is model-authored — a
  fabricated signal. Same probe distinguishes real `<system-reminder>` injections from self-written ones.

- **`settings.json` / `settings.local.json` are read once, at session start.** Editing a project's
  `.claude/settings*.json` mid-session changes nothing for the running session — `blockReadsOutsideWorkingDirectories`
  and `additionalDirectories` keep their startup values until restart. `/add-dir` is the only live fix; a
  settings edit needs a new session to take effect.

## Compact-summary parsing gotchas

- **Skill-body injection has no wrapping tag.** When a slash command fires, the skill body is concatenated into
  the *first user-turn content* as raw prose — no `<skill>` / `<command>` delimiter. The only stable marker is
  the literal string `"Base directory for this skill:"` somewhere in the blob. Forensics that count "user
  messages" by splitting on turn boundaries will wildly over-count §6 entities because the skill body's
  headers, examples, and bullet lists all look like user prose. Treat any user-turn content containing that
  literal as injected-skill-body and exclude it from §6 entity-matching corpora.
- **Sanitize pre-slice, NEVER the summary itself.** Compact-summary parsing needs two entry points into the
  message text: `_raw_message_text()` returns the un-sanitized string for the summary being analyzed;
  `extract_message_text()` sanitizes (strips `<system-reminder>`, tool-result blobs, etc.) for every *other*
  message feeding the pre-compact entity/path/decision corpus. Sanitizing the summary itself corrupts the very
  artifact under test — its 9-section structure contains legitimate angle-bracketed content (`<commit>`,
  `<path>`) that looks like injection but isn't. One function for both paths is the bug; keep them split.
- **Skill-body injection is session-start cached.**
  - **Why:** the skill body is concatenated into the session prefix at session start; mid-session on-disk edits
    to `**/SKILL.md` don't re-inject until the next session.
  - **How to apply:** when a retro or plan edits a `**/SKILL.md` the same session expects to run later (fix
    subagents, chained `/impag` → finishing → `/retro` hand-offs), commit then end the session — don't invoke
    the edited skill in the same session; its old body will still be live.

## Hook-author gotchas

- The `~/.claude/projects/<slug>/` dir is NOT a git repo. Don't run `git status`/`git add` there. Its `memory/` MAY be a symlink into a git-tracked `<repo>/.claude/memory/` (`dotfiles/scripts/link-memory.sh`); commit such writes from the repo with a pathspec (`git -C <repo> commit -- .claude/memory`), never from the slug dir.
- Snapshots dir created lazily (only on first PreCompact fire). Absence ≠ broken hook — check git log for hook
  install date vs first compaction date.
- Sub-agent JSONL files are mode 600 by default. Don't widen permissions when copying/snapshotting.
