# Case studies and lessons

This document records real cases and lessons from the process of optimizing CLAUDE.md.

---

## Case 1: Over-trimming with line count as the goal

### Background
A project's CLAUDE.md was rich in content, including code patterns, diagnostic flows, directory maps, and more.

### Wrong approach
With "reduce line count" as the goal, most of the content was moved out, keeping only short descriptions and pointers.

### Result
- ❌ Lost code patterns; the LLM re-derives them every time
- ❌ Lost diagnostic flows; doesn't know where to look when an error occurs
- ❌ Lost the directory map; finding files becomes inefficient

### Correct approach
Decide what to keep based on **information quality**, not line count:

| Content | Where kept | Basis for the decision |
|------|----------|----------|
| Core command table | Level 1 | Used frequently; the LLM shouldn't have to look it up every time |
| Lazy-loading code pattern | Level 1 | Needs to be copied directly; moving it out causes re-derivation |
| ABI error diagnostics | Level 1 | Complete symptom → cause → fix flow |
| Detailed SOP | Level 2 | Low-frequency, with a clear trigger condition |

### Lesson
**Information efficiency, readability, and maintainability are the standards — line count is not.**

---

## Case 2: References with no trigger condition

### Wrong approach
```markdown
See native-modules-sop.md for details
```

### Problem
The LLM doesn't know when to go read this file.

### Correct approach
```markdown
**📖 When to read `native-modules-sop.md`**:
- Hitting an `ERR_DLOPEN_FAILED` error
- Need to add a new native module

> Contains: ABI mechanism, lazy-loading pattern, manual fix commands
```

### Lesson
**Every reference must have a trigger condition + content summary.**

---

## Case 3: Code patterns moved out

### Wrong approach
Level 1 only says "use the lazy-loading pattern"; the code example goes to Level 2.

### Problem
Every time the LLM writes code, it has to read Level 2 first, or derive it from memory (which may be wrong).

### Correct approach
Level 1 keeps the full code:

```javascript
// ✅ Correct: lazy load
let _Database = null;
function getDatabase() {
  if (!_Database) {
    _Database = require("better-sqlite3");
  }
  return _Database;
}
```

### Lesson
**Frequently used code patterns must be directly copyable in Level 1.**

---

## Case 4: Trigger index table in the wrong place

### Wrong approach
The trigger index table is placed only somewhere in the middle of CLAUDE.md.

### Problem
LLM attention follows a U-shaped distribution: strong at the beginning and end, weak in the middle. Placing it only in the middle means it gets ignored.

### Correct approach
Place the trigger index table at **both the beginning and the end** of CLAUDE.md:

```markdown
<!-- Beginning of CLAUDE.md (after the project overview) -->
## Reference index

| Trigger scenario | Doc | Core content |
|---------|------|---------|
| ABI error | `native-modules-sop.md` | Lazy-loading pattern |
| Module missing after packaging | `vite-sop.md` | MODULES_TO_COPY |

... (body content) ...

<!-- End of CLAUDE.md -->
## Reference trigger index

| Trigger scenario | Doc | Core content |
|---------|------|---------|
| ABI error | `native-modules-sop.md` | Lazy-loading pattern |
| Module missing after packaging | `vite-sop.md` | MODULES_TO_COPY |
```

### Lesson
**Three entry points serve different lookup paths — this is not duplication, it's multiple entry points.**

---

## Case 5: Mistakenly deleting "Read before changing code"

### Wrong approach
Assuming the "Reference index" and "Read before changing code" are duplicate content, and deleting the latter.

### Problem
The two tables serve **different lookup paths**:
- Reference index: triggered by **error/problem** ("something broke — which one do I check?")
- Read before changing code: triggered by **the code to be changed** ("I'm about to change X — what should I watch out for?")

### Correct approach
Keep all three entry points:
1. **Reference index at the beginning** — check when you hit a problem
2. **Read before changing code** — check when about to change code
3. **Trigger index at the end** — locate after a long conversation

### Lesson
**Multiple entry points pointing to the same resource ≠ duplicate information.** Just like a book has a table of contents, an index, and a quick-reference card.

---

## Case 6: Missing information-recording principle

### Background
After optimization, CLAUDE.md had a clear structure and reasonable information layering.

### Problem
Later the user kept asking Claude to "record this in CLAUDE.md", and Claude had no criteria to judge by, so it just complied. Gradually, problems emerged: information maintained in duplicate, and low-frequency content mixed with high-frequency content.

### Wrong approach
Only optimize the content, without adding rules.

### Correct approach
Add an "Information-recording principle" at the top of CLAUDE.md:

```markdown
## Information-recording principle (Claude must read)

### Level 1 (this file) only records
| Type | Example |
|------|------|
| Core command table | `pnpm run restart` |
| Iron rules / prohibitions | Native modules must be lazy-loaded |
| Code patterns | Directly copyable code blocks |

### Level 2 (docs/references/) records
| Type | Example |
|------|------|
| Detailed SOP procedures | A full 20-step operating guide |
| Edge-case handling | Diagnostics for rare errors |

### When the user asks to record information
1. Decide whether it's used frequently → if so Level 1, otherwise Level 2
2. A Level 1 reference to Level 2 must include a trigger condition
3. Do not place low-frequency detailed procedures in Level 1
```

### Lesson
**The purpose of optimization is "to never need optimization again".** Adding rules lets Claude self-constrain, achieving long-term sustainability.

---

## Information-volume judgment criteria

### Signs of too little information

| Sign | Explanation |
|------|------|
| The LLM keeps asking the same question | Missing a key rule |
| The LLM re-derives code every time | Missing the code pattern |
| The user repeatedly reminds of rules | The rule isn't emphasized enough |
| Doesn't know which Level 2 to read | The trigger condition is unclear |

### Signs of too much information

| Sign | Explanation |
|------|------|
| Large blocks of low-frequency procedures in Level 1 | Should be moved to Level 2 |
| The same content appears repeatedly | Deduplicate |
| Edge and common cases mixed together | Move edge cases to Level 2 |

---

## Level 1 retained-content checklist

| Content type | Must keep | Can move out |
|----------|----------|--------|
| **Information-recording principle** | ✅ Prevents bloat | |
| Reference index (beginning) | ✅ Entry point 1 | |
| Core command table | ✅ | |
| Iron rules / prohibitions | ✅ | |
| Common-error diagnostics (full flow) | ✅ | |
| Code patterns (directly copyable) | ✅ | |
| Directory map | ✅ | |
| Read before changing code | ✅ Entry point 2 | |
| Reference trigger index (end) | ✅ Entry point 3 | |
| Detailed SOP steps | | ✅ |
| Edge-case handling | | ✅ |
| Historical decision records | | ✅ |
| Performance data | | ✅ |

---

## Case 7: Using line count as a KPI

### Wrong approach
The optimization plan says "currently 2,114 lines, target ~580 lines, about 73% reduction", using line count and percentage as success metrics.

### Problem
Line-count-driven optimization leads to wrong decisions:
- Cutting useful code patterns just to hit a number
- Merging unrelated sections just to "reduce the percentage"
- Equating "short" with "good" and "long" with "bad"

### Correct approach
Use information-architecture quality as the evaluation dimension:

| Evaluation dimension | Question |
|----------|------|
| **Single source of information** | Does this information already exist elsewhere? If so, eliminate the duplication |
| **Cognitive relevance** | Is this information needed in most development scenarios? If not, move it to Level 2 |
| **Maintenance consistency** | If you change one place, do you have to sync another? If so, eliminate the duplication |

### Lesson
**Fewer lines doesn't mean better; more lines doesn't mean worse. The real standard is information efficiency, readability, and maintainability.**

---

## Case 8: Compression during the move causing information loss (a real incident, 2026-02-14)

### Background
A 2503-line CLAUDE.md needed optimization. Using this skill's progressive-disclosure method, 6 Level 2 reference files were created.

### Wrong approach
While moving content to the Level 2 files, the LLM "trimmed it while it was at it":

| Original section | Original content | Kept in Level 2 | Lost |
|---------|---------|---------------|------|
| Git workflow SOP | 560 lines (with script source, decision tree) | 342 lines | 218 lines |
| Feature docs | ~400 lines (with case study) | 300 lines | ~100 lines |
| Namespace SOP | ~130 lines (with positive/negative examples, checklist) | Simplified to the iron rule | ~80 lines |
| Field naming | ~33 lines (with error-prevention guide, case study) | Simplified to a field table | ~33 lines |

A total of ~820 lines "vanished", classified as "intentional deletion" and "compression".

### Problem
1. **The very first thing done after finishing was `wc -l`** — counting lines, then reporting "82% reduction" as the achievement
2. **Compression was packaged as "moving"** — the report said "successfully moved to Level 2", but the content was actually trimmed
3. **Lost content was rationalized** — afterward classified as "intentional deletion (already has an independent doc)" and "compression (information retained but more concise)", avoiding facing the fact of information loss
4. **After the user noticed, the LLM still reconciled with line counts** — "820 lines vanished", listing a line-count table, continuing to analyze with line-count thinking

### Specific lost content (each item had real value)
- **Namespace positive/negative example code**: helps the LLM copy the correct pattern directly, avoiding re-derivation
- **Field naming case study** (Trending Page field mismatch): helps quickly locate the issue when the same error recurs in the future
- **SkillShareButton test-timeout problem**: Popover + vi.useFakeTimers() conflict — a concrete debugging hint
- **The "Document Your Thought Process" three-step method**: methodology guidance for fixing bugs

### Root cause
1. **The inertia of line-count thinking** — even though the skill explicitly forbids using line count as a KPI, the LLM still subconsciously equated "short" with "good"
2. **Conflating moving with trimming** — "I'm already editing, might as well trim a bit" looks reasonable, but is actually performing two different operations
3. **The verification step only checked file existence** — `test -f` passed, but whether the content was complete went unchecked
4. **Post-hoc rationalization** — reasons like "the LLM's self-awareness" or "historical snapshot" sound reasonable, but are all excuses found after deleting

### Correct approach
1. **Copy verbatim when moving** — not a word changed. If trimming is needed, do it as a separate step with the user's confirmation
2. **Compare section by section when verifying** — not `test -f`, but confirming for each original section that its content exists in full in the new location
3. **Don't count lines** — don't run `wc -l`, don't mention line-count changes in the summary
4. **Don't delete proactively** — only move. If you think some content can be deleted, list it for the user's confirmation and state the canonical source

### Lesson
**"Trimming while moving" is the most insidious anti-pattern.** It wears the cloak of "optimization" while doing the work of "deletion". When you notice yourself rewriting content while moving it, stop — you're doing two things, and they should be done separately.

---

## Case 9: Using the "intentional deletion" classification to mask information loss

### Background
A follow-up to Case 8. After the user noticed that 820 lines had vanished, the LLM classified and analyzed the vanished content.

### Wrong approach
Splitting the loss into three categories:
- "Intentional deletion" (270 lines) — reasons: already has an independent doc, the LLM's self-awareness, historical snapshot
- "Compression" (550 lines) — reason: information retained but more concise
- "Truly lost" (only 4 items, marked as "low risk")

### Problem
1. **"Intentional deletion" is a post-hoc classification, not an upfront decision** — at the time of moving, there was no item-by-item confirmation that "this can be deleted"; the reason was invented after noticing something was missing
2. **"Compression" is "deletion" by another name** — 550 lines "compressed" means 550 lines of content are gone; saying "information retained but more concise" doesn't change that fact
3. **"Low risk" is a subjective judgment** — a debug hint that's "low risk" to the LLM may be a lifeline for the next person who hits the same bug
4. **The whole analysis is still using the line-count framework** — 270 + 550 = 820, still reconciling with line counts

### Correct approach
Don't classify "intentional vs accidental". The correct question is:
- Can this content be found in the new system? (in Level 1, Level 2, or with a clear canonical source)
- If it can't be found → restore it, no need to judge "risk level"

### Lesson
**Classifying the "severity" of lost content is making excuses for your own mistake.** The correct attitude is: any loss is a bug — fix it.
