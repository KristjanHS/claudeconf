# Pre-Ship Sweeps

Checklist of cross-cutting sweeps to run before shipping a control, removal, or threshold change. Each sweep guards a class of bug where a change compiles fine but leaves the system in a contradictory state.

## Self-sabotage check before shipping a write/edit deny, path-block, or permission-tighten

Before shipping a security control (write deny, path-block, permission-tighten):
1. List the concrete file paths the control will block.
2. Cross-check against the next planned task's scope and any pending plans in `docs/plans/`.
3. Grep `docs/plans/archived/` for the same topic - a prior audit may have CUT what the current plan proposes, with documented reasoning that still applies.

If the control would block your own near-term work *or* re-adds what a sibling audit cut, either shrink its scope or explicitly accept the friction in the commit message - never ship it silently. **A control that blocks you is worse than no control.**

## Sibling-copy drift

When a security control exists as multiple physical copies (e.g. stow source + build-context-copied duplicate), edits to one silently weaken the other. On encountering drift, diff the copies and sync to the **stricter** one rather than minimally patching the weaker - the weaker copy usually exists because it was forgotten, not because it's correct.

## Threshold-moving env var sweep

Shipping an env var that relocates a behavioral threshold (max-tool-concurrency, timeout overrides, session-budget caps) isn't done at the `env:` set - grep for every downstream reader that hardcoded the old value (statusline cliffs, hook warning bands, color thresholds, docs), update them with the env. The same sweep applies in reverse when **removing** a now-obsolete threshold env var: grep every reader (statusline, session-start hook notice, tests, docs) before dropping the `env:` entry.

Without the sweep, distance-to-cliff math under-reports and warnings fire past the real trigger. **An env override pointing at X while a statusline displays "N% to cliff" against old-X is worse than no override at all.**

## Rule frontmatter vs body

When writing a `.claude/rules/*.md` file, every concrete extension or path pattern named in the rule body must also appear in the `paths:` frontmatter - the frontmatter is what gates the rule's loading, so a pattern named in the body but missing from `paths:` means the rule never loads for those files. Sweep symmetrically before commit.

## Grep user-facing prose when designing a feature removal

Removals compile fine but leave contradictory strings behind - `raise ValueError("use X for ...")` where X is being deleted, docstrings describing the removed shape, data-validation list literals naming the removed option. These survive the refactor and actively mislead users at runtime.

Before finalizing a removal design, grep:
- `raise.*Error.*"`
- `"""`-led docstrings
- `\.value\s*=\s*"` string literals

…for the thing being removed; rewrite or delete each in the same PR.

## Private→public repo sanitization sweep

When publishing a repo curated from private dotfiles, two non-obvious traps:
- A PII/secret **checker must match generic categories** (`/home/<user>/`, any email), never the author's *literal* identity - baking the real email/username into a public checker re-leaks the exact thing it scrubs.
- Sanitization covers **every tracked file, including the design/plan doc itself** - illustrative `/home/<user>/`/email examples in prose ship publicly too. Run the blocking checker over the whole tree (`git add -A` first, since it scans `--cached`) before the first push; the gate failing on your own plan doc is the sweep working.
