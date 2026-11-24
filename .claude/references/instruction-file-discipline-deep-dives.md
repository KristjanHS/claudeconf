# The five pre-authorised condense moves

Read before the first cut of a `condense` pass on `~/.claude/rules/instruction-file-discipline.md`'s subject files. Every other section of this file was rationale and was deleted 2026-08-09; the two directives it carried moved into the rule itself.

A `condense` pass needs per-item user approval because approval exists to protect *directives*. Five moves are pre-authorised — but only on text that has cleared the keep-test first. Apply in order, stopping as soon as the section reads clean.

**Keep-test — run per candidate, before any move.** Text matching any of these needs approval; only text matching none may be cut unapproved:

1. **Imperative** — must / never / only / don't, or the sentence naming the one action a step takes.
2. **The sole statement of a constraint at a trigger point a run can enter at.** A directive restated where it fires is point-of-use layering, not duplication (`condense` § Phase 2 "Not duplication — never flag"); so is an L1 directive paired with an `→` L3 pointer.
3. **A literal a run must reproduce** — a path, flag, command, marker string or shipped output form. (A 2026-07-25 impag condense nearly dropped the chain-contract token `→ plan: docs/plans/<name>.md`; a test caught it, not the pass.)
4. **A falsifier or its anchor**, or a scope-qualifier bounding the directive's extension — only when / unless / except / at most / advisory.
5. **A distinction the surrounding text doesn't otherwise carry** — the counter-example for the case people get wrong, the reason a hedge exists, a why-clause the directive can't convey on its own (§ Top three anti-patterns 1 makes that why load-bearing, not decoration).

The moves:

1. **RELOCATE** a whole entry into the file's L3 reference (uncapped), leaving the pointer — only when the reference ALREADY carries it (bodies drift into restating their own deep-dive; then the cut is free) or the content is off-normal-path (rationale, postmortem, abnormal-only branch). Relocation is byte-lossless, not load-lossless: a directive, or how-to a run must open the reference to execute, stays inline. Test each branch arm separately against the routine-case-branch trap below.
2. **DROP THE NARRATION, KEEP THE DIRECTIVE.** Datelines, SHAs, `file.ts:LINE` provenance, "caught by review", "fired for real", who-found-it, postmortem parentheticals. Git holds the story; the rule only has to hold the instruction. **Not narration:** an `(evidence → …)` pointer that anchors the rule's falsifier, or a why-clause the directive doesn't convey on its own — keep-test 4 and 5.
3. **DELETE THE EXAMPLE** only when it restates the directive in other words. Keep it when it is the counter-example for the case people get wrong, an exact literal or shipped form (keep-test 3), or what disambiguates a directive that is ambiguous without it. Test: could a run follow the directive and still get the example's case wrong? Yes → keep. Worked examples are the fattest class in these files and the easiest to over-cut.
4. **COLLAPSE A RESTATEMENT** — two lines stating one directive at different altitudes **within one trigger point** become the specific one plus a cite from the other. Across trigger points (separate steps, phases or files a run can enter at independently) both stay; collapsing those is the "merge into a weaker general one" that needs approval.
5. **DROP HEDGES AND DOUBLE-EMPHASIS** — intensifiers and formatting only: "genuinely", "actually", "always remember to", `**NEVER**` → never. Never a scope-qualifier (keep-test 4), and never emphasis the user hardened — a "re-flagged repeatedly" marker means the emphasis *is* the directive.

**Still needs approval:** deleting a directive, merging two directives into a weaker general one, dropping a falsifier or its anchor, changing a load-bearing verb (must/never/only). If a cut is ambiguous it belongs here.

**Pre-authorised is not unverified.** Decide the whole cut set before the first Edit, apply as per-item Edits (never a whole-file `Write`), then check once:

- **Never target or report a line count or % shrink.** A shrink metric rewards deletion; the pass succeeds when the section reads clean, not when it is smaller (`condense` § Phase 4).
- **Per-section survival:** for every `##` in `git show HEAD:<file>`, confirm its *content* — not just the heading — survives somewhere in the new file set.
- **Removed-imperative sweep:** `git diff -U0 -- <file> | grep '^-' | grep -E 'must|never|only|always|don.t|→'`. It fires on nearly every real pass — a clean run means each hit was re-justified as narration or still present elsewhere, not that there were no hits. Anything unaccounted for is a bug to restore, never rationalised post-hoc as acceptable compression.

**No size number triggers any of this.** These moves fire when a section is genuinely redundant, never because a byte count crossed a line.

**Move 1's bound — a routine-case *branch* is not an abnormal condition.** The commonest way a condense pass loses a directive: the body forks on a condition (branch type, project shape, platform), one arm is rarer than the other, and the rare arm gets relocated as "conditional". But "conditional" in the tier test means *the normal run never takes it* — not *some runs don't*. Test each arm separately: **if a run that takes this arm needs the text to proceed, it stays inline**, however rare the arm.
