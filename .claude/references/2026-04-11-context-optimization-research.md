# Minimizing Context Usage via AI-Agent-Oriented Documentation (2026)

Research compiled 2026-04-11 from 30+ sources including Anthropic docs, academic papers, and community practice.

Most of the original Tier 1/2/3 theory has been baked into the live system (`~/.claude/rules/instruction-file-discipline.md`, `claude-md-edits.md`, the L1/L2/L3 routing in `recording-principles.md`). What remains here is operational reference that's **not** encoded in those files.

## Startup token reference (~7,850 typical)

| Component | Tokens |
|-----------|--------|
| System prompt | ~4,200 |
| Auto memory (MEMORY.md first 200 lines) | ~680 |
| Environment info | ~280 |
| MCP tools (deferred names only) | ~120 |
| Skill descriptions | ~450 |
| ~/.claude/CLAUDE.md | ~320 |
| Project CLAUDE.md | ~1,800 |

## Compaction behavior (load-bearing)

- Reduces conversation to ~12% of original tokens
- Project-root CLAUDE.md survives (re-read from disk)
- Subdirectory CLAUDE.md files do NOT re-inject automatically
- Skill listing from startup is NOT re-injected
- Conversation-only instructions are lost

## Field-Tested Anti-Patterns

Observations from an optimization pass on a live codebase (~8.8K → ~7.9K editable baseline, ~10%):

### 1. "Tail-echo" reference indexes are waste
A second copy of a trigger table at the bottom of CLAUDE.md — placed there for "long-conversation recall" — is pure duplication. The top copy is in the system prompt and never ages out, so the bottom copy pays tokens for no benefit.

### 2. Split path-gated rule files by *subsystem*, not by file-pattern
A single `openpyxl-patterns.md` gated on 8 builder files loaded chart-specific tips for files that have no charts. Split into `openpyxl-charts.md` (gated on the one file with charts), `openpyxl-readers.md` (gated on reader files), and a narrower `openpyxl-patterns.md` core. Saved ~600 tok per typical builder session.

### 3. Critical Rules must carry their causal chain inline
Rule like "after generation, run pytest" that silently depends on a separate "Key Commands" block for the `recalc` prerequisite is fragile — a future agent can drop the block without seeing the silent-failure consequence. Fold load-bearing prerequisites (+ their failure mode) directly into the rule text.

### 4. Shell scripts beat single-command skills
A skill whose SKILL.md is one command costs ~85 tok of always-loaded description. A shell script on PATH (`~/bin/<name>`) costs 0. Reserve skills for multi-step workflows, not command aliases.
