# claudeconf — Documentation Rework for the Skeptical Reader

**Date:** 2026-06-18
**Status:** Plan, pre-build
**Branch:** `budget-hook-exact-tokens` (or a fresh `docs-skeptic-rework`)
**Driver:** `brutal-honesty-review` of the current docs, clarified via `mybrain`.

## Goal

Rewrite the reader-facing docs (`README.md`, `ADOPT.md`, `.claude/hooks/README.md`,
`docs/2026-06-18-claudeconf-design.md`) so they land with the **stated target
audience: a reader who is skeptical that any AI coding agent is worth the
trouble** and wants a concise **purpose / approach / how-to-use** for each
config, hook, rule, and skill — backed by real evidence.

The repo's content is fine. The docs are written for an enthusiast who already
uses Claude Code. This plan fixes the framing, adds proof, and makes the docs
obey the repo's own anti-bloat thesis.

## Decisions (locked via mybrain)

1. **Audience — reframe throughout.** README/ADOPT framing is rewritten
   end-to-end for a doubter: lead with the pain, plain language, every section
   justified to someone not yet sold. (Rejected: bolt-on on-ramp; split docs.)
2. **Evidence — real measured numbers.** Actual token counts and a real
   statusline screenshot, not estimates. (Rejected: labeled estimates;
   qualitative-only.)
3. **Catalog — master table + detail sections.** A single skim table at the top
   of README covering every piece (Purpose | How it works | How to use & verify
   | Evidence), with per-piece detail prose below *only* where a cell can't hold
   it. (Rejected: per-category tables; table-only.)
4. **Dedup — aggressive DRY.** Each fact stated once in a canonical home; other
   docs link to it. Author-diary (the token_monitor reversal saga) moves to the
   archived plan. (Rejected: light touch.)

### Reconciling decisions 3 and 4 (the one tension)

"Master table + detail sections" could re-introduce the bloat that "aggressive
DRY" removes. Rule for this rework:

- **Table cells are terse and canonical** — one line each, the single source of
  truth for purpose/how/use.
- **Detail sections exist only where a cell genuinely can't carry the depth**
  (the budget governor mechanism, the secret-gate layers). They **add**, never
  **restate**, the table.
- **Shared facts live in exactly one detail section.** The "shared 130k mark +
  identical measurement" fact lives in `.claude/hooks/README.md` only; every
  other mention is a one-line pointer to it.

## Findings → fixes (traceability)

| # | Finding (from review) | Fix in this plan | Phase |
|---|---|---|---|
| 1 | Zero evidence; benefits asserted, never measured | "Does this actually work?" section: real token numbers + statusline screenshot + pytest count | 0, 1 |
| 2 | Purpose/approach/how-to triad missing for rules & skills | Master catalog table + detail sections | 1, 5 |
| 3 | Docs repeat themselves (130k para ×4, two-hooks ×3) — violates own thesis | Aggressive DRY: one canonical home per fact + pointers | 1–4 |
| 4 | Jargon wall, circular definitions | Glossary near top of README; gloss each term on first use | 1 |
| 5 | No skim path; lede buried under feature list | README opens with "The problem" + skim table | 1 |
| 6 | Author-diary (token_monitor saga) in advertised design doc | Collapse to 2-sentence conclusion; move saga to archived plan | 4 |
| — | Root: audience mismatch (assumes you already believe) | Reframe throughout (decision 1) | 1, 2 |

## Phasing (by artifact — each file written once, in final form)

Phases are ordered so no file is written then rewritten. The re-work audit
(below) confirms this.

### Phase 0 — Gather evidence inputs (prerequisite for Phase 1)

These are the raw materials the README "Evidence" column and "Does this work?"
section need. Do them first so Phase 1 writes README once with real numbers in
hand.

1. **Progressive-disclosure saving.** Measure what a naive flat `CLAUDE.md`
   would carry every turn (the load-on-match `.claude/rules/*.md` +
   `.claude/references/*.md`) vs. the ~1 line each occupies in the Rules Index /
   References list.
   - **Method (locked):** reuse the repo's **existing inline usage-sum** — the
     exact `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`
     that `statusline.sh` and the budget hook's `read_last_turn_context` already
     read from the transcript's last assistant `message.usage`. **No
     `count_tokens` API, no external tokenizer** — the evidence is produced by
     the same mechanism the repo ships.
   - **Because that mechanism measures real live-session context (not standalone
     files), the figure is measured empirically:** record the reported
     usage-sum with the rules/references triggered into context vs. a turn where
     they are not, and report the delta. This is *stronger* for a skeptic than a
     static file count — it's the real number they'd watch move in their own
     statusline.
   - **Output:** the measured per-turn context delta, with the method named.
2. **Budget hook proof.** Run `pytest` from repo root; capture the passing test
   count for `tests/test_impag_budget_check.py`. The evidence is "exact 130k
   measurement, pinned by N tests," not a savings delta.
3. **Statusline screenshot.** Real `statusline.sh` render (context %,
   distance-to-stop, cost, 5h-limit) — provided by user at
   `docs/statusline.png`.
4. Stage these numbers in a scratch note (not committed) for Phase 1.

### Phase 1 — `README.md` (full rewrite, final form)

Single write incorporating reframe + lede + glossary + master table + detail +
evidence + DRY canonical homes. Target structure:

1. **One-line what-it-is** (kept).
2. **"The problem"** (NEW, ~3 lines, plain English) — long agent sessions get
   slow, expensive, and forgetful; here's the fix in one sentence. This is the
   skim-decision lede (Finding 5).
3. **"Does this actually work?"** (NEW) — statusline screenshot + the Phase-0
   token numbers + "N passing tests pin the budget hook" (Finding 1).
4. **Glossary** (NEW, ~5 lines) — compaction, progressive disclosure,
   path-gated, context cliff, fan-out (Finding 4). Gloss each on first use too.
5. **Master catalog table** (NEW) — every config/hook/rule/skill, columns
   `Piece | Purpose | How it works | How to use & verify | Evidence`
   (Finding 2). Terse cells = canonical source (decision 3/4).
6. **Detail sections** — only the budget governor and the secret gate keep
   prose, because their mechanism doesn't fit a cell. Everything else is the
   table row + a link to ADOPT for the copy-in steps.
7. **Two `hooks/` directories** distinction — keep here (canonical home); remove
   the duplicate copies elsewhere point here.
8. **Quick start + pointer to ADOPT and the design doc.**

DRY actions in this phase: the budget-governor "shared 130k + measurement"
paragraph is **removed** from README body and replaced with a one-line pointer
to `.claude/hooks/README.md`.

### Phase 2 — `ADOPT.md` (rewrite, final form)

- Reframe as the **practitioner copy-in guide** (the "I'm convinced, how do I
  adopt it" path), with plain-language justification per step.
- Remove the restated budget-governor mechanism (ADOPT:51–61) → one-line pointer
  to the hooks README canonical section (Finding 3).
- Keep the per-piece `cp` + "how to verify it worked" steps; ensure **every**
  piece has a verify step (model them on the existing bloat-gate isolation
  test). Rules and skills currently have none — add them (Finding 2).

### Phase 3 — `.claude/hooks/README.md` (becomes canonical home; trim)

- This file **owns** the "shared 130k mark + identical measurement" explanation
  and the budget-governor mechanism. Keep it; tighten it.
- Keep the "try a hook in isolation" block — it's the template for verify steps
  elsewhere.
- Remove its copy of the two-`hooks/` warning if README now owns it, or keep one
  canonical and point — pick README as canonical, leave a one-line pointer here.

### Phase 4 — `docs/2026-06-18-claudeconf-design.md` (collapse author-diary)

- Collapse the "Portability decision (key) — superseded" section to its
  2-sentence **conclusion** (exact, zero-dep, ~40 LOC inlined reader).
- Move the "superseded / reverted / bytes-4 saga" narrative into the existing
  archived plan `docs/plans/archive/2026-06-18-budget-hook-exact-portable-tokens.md`
  (it likely already lives there — verify; if so, just delete the saga from the
  design doc and point to the archive) (Finding 6).
- Update the "Audience" section to match decision 1 (skeptic, not just
  "co-workers already using Claude Code").

### Phase 5 — Rules & skills purpose lines (feed the master table)

- For each `.claude/rules/*.md` and `.claude/skills/*/SKILL.md`, confirm there's
  a one-line purpose extractable for the README table. The skill frontmatter
  `description:` already serves; rules need a one-line purpose pulled from their
  body. No file rewrites — just ensure the table cells are accurate and the
  invoke/verify column is correct (e.g. how a rule's glob fires; how a skill is
  invoked).

### Phase 6 — Verification sweep (dog-food the repo's own gates)

1. **Run `docs-bloat-gate.py`** over the new README/ADOPT — the docs must pass
   their own anti-bloat hook (density ≥ 0.45, no slop phrases). This is the
   credibility proof of Finding 3.
2. **Repetition grep** — confirm the 130k paragraph and two-`hooks/` warning
   each appear in exactly one canonical home + pointers.
3. **Link check** — every pointer (README→hooks README, README→ADOPT,
   design→archive) resolves.
4. **Secret gate** — run gitleaks + `scripts/check-hardcoded-paths.sh` over the
   tree (new screenshot path, any new files) so nothing personal ships.
5. **pytest** — still green.
6. Code review in a fresh sub-agent (`Agent(subagent_type="code-reviewer")`)
   over the doc diff before commit.

## Re-work audit (mybrain step 7)

Phases touch these files: Phase 1 = README; 2 = ADOPT; 3 = hooks README; 4 =
design doc; 5 = rules/skills (read-only for table inputs); 6 = verification.
**No file is written in two phases.** Phase 0 produces the inputs Phase 1
consumes, so README is written once with evidence already in hand (no
write-then-add-numbers rewrite). Decision: phasing is by artifact specifically
to avoid the 6× README rewrite a finding-by-finding phasing would cause. **Audit
outcome: no write-then-rewrite; phases are isolated by file.**

## External dependencies / open items

1. **Statusline screenshot** — ✅ provided by user at `docs/statusline.png`.
2. **Token-counting method** — ✅ resolved: reuse the repo's existing inline
   usage-sum (same as `statusline.sh` / `read_last_turn_context`), no API or
   external tokenizer. See Phase 0.1.

No remaining blockers — ready to execute.

## Out of scope

- Changing any hook/skill/rule **behavior** — this is a docs-only rework.
- Re-curating which pieces ship (the catalog set is settled in the design doc).
- Auto-installer / settings.json auto-merge (already rejected in design doc).
- Pushing to the remote (commits local; user pushes from the WSL host).
