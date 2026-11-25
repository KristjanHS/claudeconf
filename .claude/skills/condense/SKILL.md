---
name: condense
description: Deduplicate and consolidate CLAUDE.md, rules, and project docs (spec.md, plans, runbooks) across the hierarchy; also optimize CLAUDE.md via progressive disclosure when rules are duplicated or repeatedly ignored.
---

# Instruction + Doc Condensation

Deduplicate and consolidate CLAUDE.md / rules / project docs to remove redundancy.

## Delta-update discipline applies here too

Canonical rule: "Delta-update, never rewrite" (keep this as a rule in your own `~/.claude/rules/`). This skill is the periodic-dedup arm of that pairing. Run triggers:

- `/retro` ran or a section accumulated ≥3 overlapping bullets (existing).
- A project's bloat-override / sentinel-bypass log accumulated ≥3 entries since the last condense run (NEW).
- `<project>/docs/spec.md` crossed a 100-line growth boundary - 600, 700, 800… (NEW).

These are *reminders surfaced during `/retro`*, never auto-fire. Same posture as the "≥3 overlapping bullets" rule.

Phase 4 is per-item Edits with user approval (Phase 3); never draft a "consolidated v2" of a whole file and ship it as one Write. If a proposed change spans more than a handful of items, split it.

## Workflow

### Phase 1: Discovery

**Find all instruction + reference doc files across the hierarchy:**

Use Glob to search for both instruction files and project-doc reference files. The corpus extends beyond CLAUDE.md so cross-file dup detection catches drift between rules and the docs they mirror.

1. `**/CLAUDE.md` and `**/CLAUDE.local.md` in the project root
2. `.claude/rules/*.md` in the project root
3. `~/.claude/CLAUDE.md` (global personal instructions)
4. `docs/spec.md` (NEW - project reference doc)
5. `docs/human/*.md` (NEW - human-facing runbooks, e.g. cloud-env-setup)
6. `docs/plans/*.md` (NEW - top level only; see non-targets below)

**Explicit non-targets** (skip even when matched by broader globs):
- `docs/plans/archived/**` - frozen post-mortems, never modified.
- `docs/analysis/**` - `.claudeignore`'d one-off audits.

**Read all discovered files and analyze for:**
1. Intra-file duplication (same instruction repeated within a file)
2. Cross-file duplication (same instruction in multiple files, or same point in `docs/spec.md` AND a rule, or `docs/spec.md` AND `CLAUDE.md`)
3. Misplaced instructions (subdirectory files containing project-wide content)
4. Trigger-table drift (NEW)
5. Plan supersession (NEW)
6. Section-size flagging (NEW)
7. Disclosure candidates in CLAUDE.md (see Progressive-disclosure mode)

### Phase 2: Analysis

**Intra-file duplication:**
- Identify repeated bullet points or instructions
- Find semantically similar content (different wording, same meaning)

**Cross-file duplication:**
- Root CLAUDE.md should contain project-wide instructions
- Subdirectory CLAUDE.md should only contain directory-specific instructions
- If an instruction appears in both root and subdirectory, keep only in root
- If an instruction in subdirectory applies to whole project, move to root
- Same point in `docs/spec.md` AND a rule, or `docs/spec.md` AND `CLAUDE.md` → keep in the more specific file and replace the other with a `→ see <path> §<heading>` pointer

**Misplaced instructions:**
- Subdirectory file contains instructions that apply project-wide → move to root
- Root file contains instructions only relevant to one directory → move to subdirectory

**Trigger-table drift:**
- CLAUDE.md keeps a reference index whose "Read" column points to `docs/spec.md` § headings.
- Parse the trigger-table rows; for each `docs/spec.md`-typed target, grep the spec for a matching `## ` or `### ` heading.
- Flag rows whose target heading no longer exists or was renamed. Default action: flag-only with the closest existing heading shown side-by-side; promote to propose-and-apply only if the user repeatedly takes the obvious fix.

**Plan supersession:**
- For each `docs/plans/*.md` (top level only - archived plans excluded), grep for `SHIPPED`, `DONE`, `landed`, `archived to`.
- When a marker appears next to verbose pre-ship phase prose, flag the section above as a collapse-candidate. Proposed Edit replaces N lines of phase prose with one done-line citing the marker (e.g. `*Shipped 2026-04-28 in commit `abc1234` - see `docs/plans/archived/<file>.md`.*`).

**Section-size flagging:**
- For `docs/spec.md`, walk L2 headings and measure char count per section.
- Flag any section >1500 chars. If you run a docs-bloat gate (a hook that blocks oversized doc sections), mirror its per-section character threshold here - sections that would no longer qualify for a heading exemption are dedup/split candidates.

### Phase 3: Interaction

Present findings using AskUserQuestion with checkboxes.

**For each issue found:**
1. Show the duplicated, misplaced, or drifted content
2. Identify which files are affected
3. Propose the consolidation (delete, move, merge, or replace-with-pointer)

Trigger-table drift findings render old-row → closest-heading side-by-side. Plan supersession findings show "collapse N lines into 1 done-line" with the proposed replacement text.

**Example:**
```
Issue: "Use 2-space indentation" appears in both ./CLAUDE.md and ./src/CLAUDE.md
Proposal: Remove from ./src/CLAUDE.md (already covered by root)
```

Wait for user approval before implementing.

### Phase 4: Implementation

For approved changes:

1. **Remove duplicates** - Delete redundant entries, keeping the most appropriate location
2. **Move misplaced content** - Transfer instructions to correct hierarchy level
3. **Merge similar items** - Combine semantically similar instructions into one
4. **Replace duplicates with pointers** - When two files held the same point and one is now canonical, replace the other with `→ see <path> §<heading>`

**Gate-aware pre-check (advisory, not blocking).** If your project runs a docs-quality gate (a hook that blocks low-quality or oversized doc edits), pre-check each approved Edit on `docs/spec.md` (or any other gated path) against the same rules the hook uses *before* applying - so you reword ahead of the block rather than after it:

1. Compute the proposed `new_text`.
2. Run the gate's "slop term" / banned-phrase check on `new_text` - if it would trip, surface to the user: "This Edit would trip the docs gate with terms: [...]. Reword?"
3. For longer additions, run the gate's lexical-density / readability check - if it would fall below the threshold, surface to the user.
4. A pure char-delta size cap is usually **not** pre-checked. Condense Edits are usually subtractive; on rare additive cases the sentinel bypass is the right escape hatch.

Pre-check failures are advisory - the user can proceed (and the hook stays the unbypassable line of defence). The point is to reword *before* the hook blocks rather than after.

**Hierarchy rules:**
- `./CLAUDE.md` - Project-wide instructions (highest priority)
- `./.claude/rules/*.md` - Topic-specific rules (modular)
- `./docs/spec.md` - Project reference docs (CLAUDE.md trigger-indexed; section-sized for spec tier)
- `./subdir/CLAUDE.md` - Only instructions specific to that subdirectory
- `~/.claude/CLAUDE.md` - Personal preferences across all projects
- `./CLAUDE.local.md` - Personal project-specific (not shared)

## Progressive-disclosure mode

Run it when CLAUDE.md rules are duplicated or keep getting ignored, or Claude re-derives the same code pattern each session. Long, rarely needed content moves out of CLAUDE.md and a one-line pointer stays.

Findings still go through Phase 3 for approval, and Phase 4 applies them.

**Classify each CLAUDE.md section:**
- Stays: core commands, iron rules and prohibitions, copyable code patterns, error diagnostics (symptom → cause → fix), the directory map, the reference index.
- Summary and trigger stay, body moves: SOPs (keep the key pitfalls), config examples (keep the one or two common ones), API docs (keep common signatures).
- Moves whole: decision history, performance data, tech-debt lists, edge cases.
- Neither triggered nor reference material: propose deleting it, name its canonical source, and keep a pointer to that source.

**Pick the target:**
- Path-specific (one language, directory or tool) → `.claude/rules/<topic>.md`, with a `paths:` glob for every file type it governs.
- Reference-shaped (long checklist, SOP, postmortem) → `docs/references/<topic>.md`, or `~/.claude/references/<topic>.md` for user-level content.
- Never move a directive, or how-to a normal run needs in order to proceed, into a reference.

**Move verbatim.** Copy the passage as-is. You may add headings; don't trim, reword or merge it on the way. Trimming is its own condense item with its own approval.

**Every pointer names its trigger.** A bare "see x.md" rarely gets opened. Say when to open the file and what's in it:

```markdown
**Read `docs/references/native-modules.md` when:** `ERR_DLOPEN_FAILED`, or adding a native module. Holds: ABI notes, lazy-load pattern.
```

With several references, use tables: a problem index near the top (`symptom | doc | holds`) and a read-before-changing table (`what you change | doc | key pitfall`).
Both may point at the same doc. That is two entry points, not duplication, so Phase 2 leaves them alone. A copy of the problem index at the end of the file helps in long sessions.

If CLAUDE.md has no rule for where new notes go, propose one at the top: used often → CLAUDE.md, otherwise a reference with a trigger pointer.

**Verify.** Set `F` to the CLAUDE.md path (repo-relative, e.g. `.claude/CLAUDE.md`). Commit it before editing if git doesn't track it yet. All three must pass before closing:
1. Every referenced file exists (exits non-zero on a missing one or a bad `F`):
   `test -f "$F" && grep -oE '(~/\.claude|\.claude|docs)/[A-Za-z0-9_./-]+\.md' "$F" | sed "s|^~|$HOME|" | sort -u | xargs -r ls > /dev/null`
2. Every `##` section of `HEAD:$F` survives in full: in `$F`, in the file it moved to, or in a named canonical source. Screen headings first (exits non-zero and prints each missing one), then compare content section by section:
   `git cat-file -e HEAD:"$F" && ! git show HEAD:"$F" | grep '^## ' | while read -r h; do cat "$F" $(find docs .claude/rules ~/.claude/references -name '*.md' 2>/dev/null) | grep -qxF -- "$h" || echo "NOT FOUND: $h"; done | grep .`
3. A shortened or missing passage gets restored, not sorted into "intentional deletion". Don't count lines or report line deltas.

## Resources

This skill is self-contained. If you also keep a `reflect`-style skill, it may ship helpers worth reusing here:

- A "locate all CLAUDE.md files" script (the same Glob discovery Phase 1 does by hand).
- A memory-locations reference (the memory hierarchy details).
- An anti-patterns reference (what to avoid when writing instructions).

None are required - Phase 1's Glob discovery and the hierarchy rules above cover the mechanism on their own.
