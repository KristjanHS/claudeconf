---
name: Instruction file content discipline
description: Content discipline for CLAUDE.md, .claude/rules/**, and .claude/references/** — prevent bloat that requires later condensation
paths:
  - "**/CLAUDE.md"
  - "**/.claude/rules/**/*.md"
  - "**/.claude/references/**/*.md"
---

# Instruction File Content Discipline

Cadence (when to ship CLAUDE.md edits vs batch) lives in `claude-md-edits.md`. This rule covers **content quality** — what belongs at which tier, and what to check before adding a bullet.

## Top three anti-patterns

1. **"Why this rule exists" as a default template.** It's optional and most cases don't need it. Add only when the rule text doesn't convey the reason. Project-specific incident detail goes in commit messages or in the *project's* rule file, never in global rules.
2. **Append-without-grep.** New bullets land beside near-duplicates because authors don't grep the file first. Adding content and dedup'ing content are the same step — don't outsource dedup to a later cleanup pass.
3. **Project-specific rationale in global rules.** A "Why" naming a date / `file.py:line` / project-only path means the rule belongs in *that project's* `.claude/rules/`. Global rules carry the *generic* habit; the incident lives where it happened.

## Tier discipline (L1 / L2 / L3)

- **L1** = `CLAUDE.md` — always loaded, ~6k token budget. Cross-cutting habits + pointers.
- **L2** = `.claude/rules/**/*.md` — path-gated; loads only when matching files read/edited. Topic-specific operational rules.
- **L3** = `.claude/references/**/*.md` — on-demand; loads only when an L1/L2 pointer fires. Long checklists, postmortems, recovery procedures.

**Rules:**
- L1 bullet that's path-specific (Python, hooks, a particular file type) → move to L2.
- L1 bullet that's a >3-sentence checklist or postmortem → move to L3, leave a 1-line pointer.
- L2 rule that exists in both global and project with similar content → consolidate at the narrower tier (project usually wins; global only if truly cross-project).
- **Project-specific incident *archives* go to L3 (`docs/` or `~/.claude/references/`), NOT L2 (`.claude/rules/`).** Rules carry the generic habit; archives carry the history. An incident archive given `paths:` frontmatter auto-loads on every matching file edit and duplicates context already loaded from the global rule the incident drove. Route via the project's `CLAUDE.md` trigger table instead.

## No duplication of path-gated rules in CLAUDE.md

If a rule file already covers the topic (e.g. `reading-large-files.md` for large-file thresholds), do **not** restate it in CLAUDE.md. Path-gated rules auto-load when relevant; restating them in L1 burns always-loaded tokens for context-specific content.

**How to apply:** before adding an Efficiency or Iron Rule item, grep `~/.claude/rules/` and `<project>/.claude/rules/` for the topic. If found, either consolidate at L1 (delete the L2) or skip the L1 addition. Never both.

## Multi-bullet shape pattern → extract to reference

When **≥3 bullets share a checklist shape** (pre-flight sweeps, debugging workflows, removal patterns, recovery procedures), extract to a single L3 reference and replace with one L1 pointer. The pointer carries the trigger language; the details live where they don't burn always-loaded tokens.

## Stale-name sweep before naming project conventions

When a bullet names a project convention (directory layout, file paths, branch names, env var names), grep the current state before committing — pasted-in content from another project or an older session may carry a name the current project no longer uses.

## Delta-update, never rewrite

Append a new bullet/section, or Edit the specific line that's wrong. Do not regenerate the file or rewrite a section wholesale.

**Why:** Each existing bullet is the residue of a specific incident; wording is often load-bearing in ways the current text doesn't show. "Says the same thing more cleanly" silently drops that history.

**How to apply:**
- Adding new guidance → append, even if it overlaps slightly. Overlap is a dedup candidate, not a rewrite trigger.
- Fixing wrong guidance → Edit the specific phrase. Don't rewrite the surrounding paragraph.
- Cleanup spanning multiple bullets → stop. That's a `condense` pass — run as its own task with per-item user approval.
- Tool: prefer `Edit` with a narrow `old_string`; `Write` only for new files.

## Write-time default: 1 sentence

New rule bullet starts at 1 sentence. The surrounding bullets may be long — don't pattern-match on neighbours. ("Why" template guidance: see anti-pattern 1 above.)

## SKILL.md authoring discipline

SKILL.md body is loaded into the session prefix the moment the skill matches and stays there for the rest of the session — body bloat is *more* expensive than CLAUDE.md bloat. Apply tier discipline asymmetrically: a 200-line skill body is a heavier ongoing cost than a 200-line rule file (which only loads on path match).

**Body target: ≤100 lines.** Workflow steps + the minimum trigger logic. Detailed playbooks (technique libraries, anti-pattern tables, installation procedures) go to L3 references and are linked from the body.

**Don't include:**
- "Quick Reference" / "Summary Table" sections that restate the body in compressed form. Pick one representation, not both.
- "Common Commands" / "Quick Start" sections listing tool invocations the user (not Claude) runs. These are tool documentation, not skill behavior.
- "Related Skills" / "Getting Help" / "Why this matters" trailers — pure word count with no behavior. If a related skill is genuinely needed, name it inline at the trigger point.
- Implementation details for UI/output formatting (ANSI color palettes, terminal escape codes). Belongs in the script that emits the output, not the skill body.
- Harness-internals documentation (PostToolUse hook mechanics, cache TTL specifics, statusline color thresholds). Document those in the hook script or in a dedicated reference.
- Closing "Remember", "Notes", "Important", or motivational prose after the last actionable step. Skills end at the final step — anything that follows is restated body or vibes, both pure cost.

**Description field:** one-line trigger language. No "Examples:" lists, no "e.g., …" elaboration — those bloat the always-indexed description and offer no behavior.

## Symmetric verbs in checklists

For every `add` / `grep` / `record` / `document` add-verb in a checklist, pair a concrete subtract-verb (`delete` / `remove` / `unlink`). Asymmetric verbs generate one-way bloat: contributors add new entries because the checklist tells them to, but no step ever instructs removal, so dead entries accumulate forever. When writing or reviewing a checklist, scan each numbered step — if it only ever grows the artifact, add a sibling step that prunes it.

## Pre-commit self-review checklist

After editing CLAUDE.md or a rule/reference file, before commit:

1. Is anything in the diff already covered by a path-gated rule? → delete the duplicate.
2. Does any new bullet name a project-specific incident (file:line, date, project-only path)? → move to that project's rule.
3. Are 3+ bullets in a row sharing a shape? → extract to a reference, leave one pointer.
4. Is any bullet >100 words? → compress to ≤2 sentences or move the prose body to a reference.
5. Did this edit add a sibling to a list that's now ≥4 items of the same kind? → extract the whole list.
6. Does any project-convention name still match current state? → grep to confirm.

If yes to any: revise before commit. The condense skill exists because this discipline wasn't applied at write-time; cheaper to apply it now than to clean up later.
