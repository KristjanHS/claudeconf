# Outline-first file reading (extended notes)

Extracted from the path-gated rule `reading-large-files.md` so the always-loaded footprint stays tight. Read when the rule tells you to, or whenever you're about to queue up 2+ overlapping offset Reads on the same file.

## Outline-first decision tree (multi-section structural understanding)

When you need to understand how a 300–800-line file is *organized* (where the main function starts, where the data-write loops are, where the totals/return live) — **not** a specific symbol lookup and **not** a one-window sample — two or three broad offset Reads covering 60%+ of the file is the wrong shape. Each overlapping offset Read fully re-tokenizes its range (no harness dedup); three 200-line ranges ≈ one full read at ~5–6k tokens.

Ordered cheaper path:

1. **Outline grep** (~40 tokens): `grep -En "^def |^class |^async def " <file>` returns every top-level signature + line number. That IS the structural map for most builder-style modules.
2. **Targeted windows** (~100–200 tokens): for the 2–4 signatures you actually need to inspect, `Read(offset=N-5, limit=40)` each. Don't read the whole function body unless you'll edit inside it.
3. **Subagent if still unclear** (0 main-context tokens): dispatch `Agent(subagent_type="Explore")` with "summarize the builder pattern in <file> — where does the main function start, where are the write loops, what does it return". The subagent reads the full file in its own context; only the summary comes back.

**Threshold:** if the goal is structural coverage ≥70% of the file, a subagent beats three offset Reads — the subagent's final summary is 200 tokens vs. the three Reads' 4–6k.

**Anti-pattern (the one this section closes):** offsets 1–120, 150–400, 400–730 on a 726-line file. Covers the whole file at full cost with none of Grep's dedup benefit. If three offset Reads are queued up, switch to step 1.

## Declare-intent examples (companion to the rule's "Declare intent before reading" bullet)

If the goal is "find the FOO function", Grep beats Read; if it's "understand the module's top-level structure", `Read(offset=0, limit=80)` beats a full read.

## Silent session-budget warning

A single naïve full read of a 50K-line `pnpm-lock.yaml` or a 1500-line source file silently burns a large slice of the 200k session-stop budget at opus/effort=high. The harness will not warn you — the 25K-token ceiling truncates the content but still charges the tokens against your budget, and repeated reads compound.

## Why this rule exists

CLAUDE.md Efficiency note: "A full read of a 1000-line file is ~8K tokens; multiple full reads silently burn the 200k session-stop budget." The `reading-large-files.md` rule extends that to the specific extensions and size thresholds where the problem is near-certain.
