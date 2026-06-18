# Global Claude Instructions - Example Skeleton

> **This is a teaching skeleton, not a finished config.** Copy it into your own
> `~/.claude/CLAUDE.md` and adapt the placeholders to your environment. The
> structure is the lesson: a short always-loaded L1 file that *points* at
> heavier content instead of inlining it.
>
> **Progressive disclosure** is the context-saving idea behind this layout.
> Path-gated rules (`.claude/rules/*.md`) auto-load **only when you read or edit
> a file their frontmatter `globs` match** - and references load **only when a
> pointer fires**. So topic-specific guidance stays out of every prompt and
> costs tokens only when it's actually relevant, keeping the always-loaded
> context lean.

<!-- L1 = this file (always loaded) · L2 = ~/.claude/rules/ (path-gated) · L3 = ~/.claude/references/ (manual pointer) -->

## References (read when triggered)

L3 references live in `~/.claude/references/` and load only when one of these
pointers fires. These are real, working examples shipped with this catalog -
adapt or extend them:

- `~/.claude/references/2026-04-11-context-optimization-research.md` - optimizing CLAUDE.md/skills/rules for token usage; startup-token + compaction reference.
- `~/.claude/references/reading-large-files-outline-first.md` - about to queue 2+ overlapping offset Reads on one file, or the `reading-large-files` rule points here.
- `~/.claude/references/subagent-dispatch.md` - sub-agent dispatch (parallelization, Plan/Explore/general-purpose, background Bash, worktrees).
- `~/.claude/references/pre-ship-sweeps.md` - pre-ship checklists (deny/path-block/permission/threshold/feature-removal/repo-sanitization).
- `~/.claude/references/recording-principles.md` - "record this" / "remember this", or organizing docs (L1/L2/L3 routing).
- `~/.claude/references/anti-patterns-common-rationalizations.md` - naming the rationalizations behind skipping a process gate (debugging/design).

## Iron Rules

Always-on safety/operational rules. Keep this list short - it's loaded every
turn. Examples (adapt or replace):

**CWD Discipline**: Use absolute paths for all tool calls. Never `cd` into a subdirectory for a one-off command - it shifts CWD and breaks subsequent commands.

**Hooks**: After any hook config change, confirm no errors appeared. Hook error annotations are not always surfaced in tool results.

**Durable storage**: Never write docs/plans to a folder that isn't version-controlled. Project-specific docs → `<project>/docs/`; cross-project notes → `~/.claude/references/`.

**Secret-file reads**: Never open `.env*`, `id_rsa`, `*.pem`, `*.key`, `credentials.*` unless explicitly asked - they leak into transcripts and compaction snapshots unredacted. Ask for the value to be pasted instead.

**"Internal error" ≠ command failed**: A transport failure does not mean the command didn't run. Probe state with a read-only `ls`/`cat` before retrying anything destructive.

## Interaction Style

- For multi-session work, stub a doc and append per section so an interrupted session is recoverable. For single-session analyses, default to conversation output + commit messages.
- When presenting alternatives, prefer the highest-maturity option.
- After destructive changes to shared-wiring paths (`~/.claude/`, `settings*.json`), run a verification sweep: JSON parse, resolve symlinks, grep settings for refs to deleted paths.

## Efficiency

- Don't re-read files already in context. After a successful Edit, no verification read needed.
- Read/Write track by exact path. Read the path you intend to Edit/Write.
- **Git recon**: `git status --short` + `git log --oneline -5`. Skip a plain `git diff` for in-session edits - the Edit result is the diff.
- **Code review runs in a fresh sub-agent** so it doesn't inherit the author's rationalizations.

## Rules Index (path-gated - auto-loaded when matching files are read/edited; globs in each file's frontmatter)

| Rule file (`~/.claude/rules/`) | Topic |
|-----------|-------|
| `reading-large-files.md` | Force `offset`/`limit` or Grep; ≥800-line threshold for py/md |
| `claude-md-edits.md` | Batch CLAUDE.md edits to session boundaries - mid-session breaks cache |
| `testing.md` | Test value gate (5 checks), ratio discipline |
| `instruction-file-discipline.md` | Tier discipline (L1/L2/L3); keep project-specific incidents out of global rules |
