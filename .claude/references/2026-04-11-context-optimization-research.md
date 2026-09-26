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

## Field-Tested Anti-Patterns (2026-04-15 session)

Observations from an optimization pass on a live codebase (~8.8K → ~7.9K editable baseline, ~10%):

### 1. "Tail-echo" reference indexes are waste
A second copy of a trigger table at the bottom of CLAUDE.md — placed there for "long-conversation recall" — is pure duplication. The top copy is in the system prompt and never ages out, so the bottom copy pays tokens for no benefit.

### 2. Split path-gated rule files by *subsystem*, not by file-pattern
A single `openpyxl-patterns.md` gated on 8 builder files loaded chart-specific tips for files that have no charts. Split into `openpyxl-charts.md` (gated on the one file with charts), `openpyxl-readers.md` (gated on reader files), and a narrower `openpyxl-patterns.md` core. Saved ~600 tok per typical builder session.

### 3. Critical Rules must carry their causal chain inline
Rule like "after generation, run pytest" that silently depends on a separate "Key Commands" block for the `recalc` prerequisite is fragile — a future agent can drop the block without seeing the silent-failure consequence. Fold load-bearing prerequisites (+ their failure mode) directly into the rule text.

### 4. Shell scripts beat single-command skills
A skill whose SKILL.md is one command costs ~85 tok of always-loaded description. A shell script on PATH (`~/bin/<name>`) costs 0. Reserve skills for multi-step workflows, not command aliases.

### 5. Replace runtime environment probes with cwd pattern-matching
`[ -f /.dockerenv ]` and `test -d /workspaces` before every push is a per-session roundtrip. The cwd from the Environment block already tells you: `/workspaces/...` = devcontainer, `/home/<user>/projects/...` = WSL host. Encode the disambiguation in the rule itself.

## Measured cost model (2026-07-09) — supersedes "cache_read dominates"

Full analysis: `~/projects/dotfiles/docs/research_results/context-cost-model.md`. Distilled:

- **The bill is three near-equal thirds**, not one term: cache_read 35% / cache_write 33% / output 30% / fresh input 2% (1,504 deduped API calls, 126.4M context tokens). cache_read is huge in token count and modest in cost because it bills at `0.1×`.
- **Price of a token entering context** = `1.25 + 0.1 × (calls remaining)`. Measured: each entering token is re-read ~13.4×, so it averages ~2.6× base input. A 10k-token read with 30 calls left costs ~42k billed tokens; delegated to a subagent returning a conclusion, ~2k.
- **Output is 30% of the bill and 73% of it is unpersisted reasoning.** Prose is ~2.4% of the bill — not a lever. `Write`-vs-`Edit` is ~1.3% — not a lever.
- **Batching is the top lever (~16%)**: an avoided API call saves the context re-read *and* the reasoning tokens it would regenerate (≈13k billed tokens). 84% of tool-bearing calls currently carry exactly one tool.
- **Cold prefix re-writes cost 6.5%.** Only ~1.6% is 5-min-TTL expiry from user-latency gaps; the rest is mid-session prefix mutation (`ToolSearch` schema fetches, `Skill` body injection, skill-listing deltas). Load skills/tools in the first turn.
- **The startup floor** (median 31,711 tok) is re-read every call = ~14% of the bill; trimming 10k saves ~4.5%.
- **Measurement trap**: `message.usage` is duplicated onto every content-block record — dedupe by `requestId` or over-count ~3.4× (see `claude-code-persistence.md`).

## Stow symlinks double-load CLAUDE.md as `nested_memory` (fixed 2026-07-09)

Touching any file under a stow package that contains `.claude/CLAUDE.md` makes Claude Code attach a **second copy** of that file (~3.8k tok) on top of the one already in the system prompt. Memory loading (`nee()`) realpath-dedupes *within* a discovery pass but not *across* passes: the User copy (`~/.claude/CLAUDE.md`) and the nested Project copy (`<repo>/claude/.claude/CLAUDE.md`) travel different channels and share no dedupe set.

- **Fix**: `claudeMdExcludes: ["**/claude/.claude/CLAUDE.md"]` in `~/.claude/settings.json` — picomatch globs over *absolute* paths; applies to User/Project/Local memory types only. Matched on the pre-symlink-resolution path, so it kills the Project copy and leaves the User copy intact.
- **Path-gated `rules/*.md` do NOT double-load** — they attach once, at their realpath. A rule reached via `~/.claude/rules/x.md` is attributed to `<repo>/claude/.claude/rules/x.md` in *every* project, so the nested-discovery hit dedupes against it by path string.
- **`.claudeignore` and `git check-ignore` are both irrelevant here.** `.claudeignore` is unimplemented (string absent from the binary; anthropics/claude-code#4160). `git check-ignore` (`yvn()`) gates *skill* discovery only, never memory.
