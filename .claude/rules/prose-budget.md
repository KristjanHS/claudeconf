---
name: Unasked prose budget
description: Text written without an explicit ask for that text — .md, docblocks, comments, test names, memory — admits a value, a move or a falsifier, in at most two lines per unit.
paths:
  - "**/*.md"
  - "**/SKILL.md"
---
# Unasked prose — two lines, three admitted kinds

One rule, every surface a session writes: docs, plans, auto-memory (`project_state.md`, `roadmap.md`),
instruction files, docblocks, inline comments, block banners, `describe`/`it` strings, config comments.

## The unit and its ceiling

A **unit** is one bullet, one `##` section body, one comment block, one docblock, one test name. **A unit
is at most two lines.**

This is a shape check on the text about to be written, never on a file. Nothing measures, opens or trims
an existing file (`~/.claude/references/memory-system.md` §No size caps still binds everywhere else), and
**no hook blocks the write** — a refused write costs more than the prose it refuses.

**An Edit that absorbs a near-duplicate into an existing bullet writes that WHOLE bullet** — the merged
result is the unit, and it clears the two lines, or the absorb doesn't happen and the two bullets stand
(`instruction-file-discipline.md` §anti-pattern 2). Absorption is the one way a unit grows past the ceiling
without any single write breaching it.

Overflow does not become a third line, a nested bullet, a sibling unit, or a new doc that inherits the
paragraph. It goes to the **commit message**: durable, greppable, attached to the diff, free to every
future reader.

## Three admitted kinds — a whitelist

A unit carries exactly one of:

- the **live value** — a cut, a weight, a path, a symbol, a name;
- the **move** that binds the next edit — an imperative or a prohibition;
- the **falsifier** — a command that can return non-zero.

Everything else is refused **whatever it is labelled**. "Live constraint", "gotcha", "context", "trap"
and "worth carrying" are labels, not kinds; a mechanism explanation relabelled as a constraint is still
refused. **The move-kind also requires that an edit is actually coming — ask "is this owed: would someone
act on it now?" before asking which file it goes in.** A note on something you already decided not to do
binds no next edit; it is a status wearing an imperative, and its record is the commit message that closed
it. The item's own hedge (*nice-to-have, parked, refuted, wontfix, benign, unreachable today*) is the
refusal trigger, never a qualifier that earns it a line. (Rationale, five-whys, session narrative, rejected options, status snapshots, and measurements a
probe or commit already holds fail the whitelist without needing their own clause.)

## Length is granted per artifact, never per session

An explicit ask for **this text** — "write it up", "explain it in the file", "full walkthrough" — grants
length. A user-initiated **session** grants none: an impag run, a finish report, a retro and a plan
execution are requested work whose individual writes are still unasked. Never pattern-match shape off the
surrounding file — most of it predates this rule.

**A seam is not an escape hatch.** A rule routing an overflow line to "its seam" (`claude-md-edits.md`
§One in one out, `instruction-file-discipline.md` §Write-time checks) grants the two lines at that seam,
not a paragraph: a line too expensive for an always-loaded file is not free in a docblock.

## Every add pairs with a delete, at the same write

A new value **overwrites** the one it supersedes; a behaviour change **rewrites** the sentence it
falsifies. ⛔ `⛔ SUPERSEDED` banners, `## rulings round 3` logs, precedence headers (`these WIN over
§3`), `NOTE: the above is now …`, retired-then-reinstated stacks. `git show` / `git blame` keep what you
removed — never at ship, never on a schedule.

**Net-new prose has no delete to pair with, so it goes to the commit message.** A comment, docblock, `##`
section or test name that supersedes no existing line and spells as none of the three kinds is not
shortened to fit the two-line unit; it is not written.
