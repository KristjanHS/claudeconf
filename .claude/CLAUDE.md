# Global Claude Instructions: Example Skeleton

Adapt, don't copy as is: see [ADOPT.md §1](../ADOPT.md#1-the-claudemd-skeleton).

## References (read when triggered)

- `~/.claude/references/2026-04-11-context-optimization-research.md`: optimizing CLAUDE.md/skills/rules for token usage; startup-token + compaction reference.
- `~/.claude/references/reading-large-files-outline-first.md`: about to queue 2+ overlapping offset Reads on one file, or the `reading-large-files` rule points here.

## Iron Rules

**CWD Discipline**: Use absolute paths for all tool calls. Never `cd` into a subdirectory for a one-off command; it shifts CWD and breaks subsequent commands.

Hooks: After any hook config change, confirm no errors appeared. Hook error annotations are not always surfaced in tool results.

Durable storage: Never write docs/plans to a folder that isn't version-controlled. Project-specific docs → `<project>/docs/`; cross-project notes → `~/.claude/references/`.

**Secret-file reads**: Never open `.env*`, `id_rsa`, `*.pem`, `*.key`, `credentials.*` unless explicitly asked, because they leak into transcripts and compaction snapshots unredacted. Ask for the value to be pasted instead.

**"Internal error" ≠ command failed**: A transport failure does not mean the command didn't run. Probe state with a read-only `ls`/`cat` before retrying anything destructive.

## Interaction Style

- For multi-session work, stub a doc and append per section so an interrupted session is recoverable. For single-session analyses, default to conversation output + commit messages.
- When presenting alternatives, prefer the highest-maturity option.
- After destructive changes to shared-wiring paths (`~/.claude/`, `settings*.json`), run a verification sweep: JSON parse, resolve symlinks, grep settings for refs to deleted paths.

## Efficiency

- Don't re-read files already in context. After a successful Edit, no verification read needed.
- Read/Write track by exact path. Read the path you intend to Edit/Write.
- Git recon: `git status --short` + `git log --oneline -5`. Skip a plain `git diff` for in-session edits. The Edit result is the diff.
- Code review runs in a fresh sub-agent so it doesn't inherit the author's rationalizations.

## Rules Index

| Rule file (`~/.claude/rules/`) | Topic |
|-----------|-------|
| `reading-large-files.md` | `offset`/`limit` on large files |
| `claude-md-edits.md` | Batch edits; don't break cache |
| `testing.md` | Test value gate |
| `instruction-file-discipline.md` | Tier discipline (L1/L2/L3) |
| `external-sources.md` | Outside code is read-only; run via a reviewed entry point |
| `github-actions.md` | Run workflow jobs locally with `act` |
| `hooks.md` | Hook I/O gotchas; confirm no settings errors |
| `prose-budget.md` | Keep unasked-for prose short |
| `python-refactors.md` | Import/module refactor traps |
