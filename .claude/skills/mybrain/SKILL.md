---
name: mybrain
description: Refine rough ideas into designs via questioning and ideation, before creative or strategic work.
---

# Brainstorming Ideas Into Designs

Turn ideas into fully formed designs through collaborative dialogue, structured ideation, and incremental validation.

Start by understanding the current project context, then ask questions one at a time to refine the idea. Once you understand what you're building, present the design in small sections, checking after each section whether it looks right.

---

## Mode Selection

At the start of every session, assess complexity and offer a choice:

**Quick mode** -- Focused, well-scoped problems where the user mostly knows what they want. Clarify, propose approaches, design. Typical: 4-6 questions, 10-15 minutes.

**Deep mode** -- Complex, ambiguous, or creative challenges where the problem space needs exploration. Adds structured ideation techniques (perspective shifts, inversion, constraint play, analogical transfer) before converging. Typical: 8-12 questions + ideation rounds, 20-40 minutes.

If unsure, briefly describe both and ask. Default to Quick if scope is narrow. Suggest Deep when: the problem is ambiguous, multiple stakeholders are involved, the user says they're "stuck", or innovative solutions matter more than speed.

The user can switch modes mid-session. If Quick reveals unexpected complexity, suggest upgrading. If Deep feels like overkill, offer to skip ahead.

---

## Scope Check

Before asking detailed questions, assess scope. If the request describes multiple independent parts (e.g., "build a platform with chat, file storage, billing, and analytics"), flag this immediately.

If too large for a single design, help break it into sub-projects: what are the independent pieces, how do they relate, what order should they be tackled? Then brainstorm the first sub-project through the normal flow. Each sub-project gets its own spec, plan, and implementation cycle.

---

## Quick Mode Process

### 1. Understand Context

- Read relevant project files, docs, and recent commits
- Ask about background: what exists already, what prompted this, who is the audience, what constraints matter
- Do NOT assume context -- ask

### 2. Clarify

- **One question per message** -- do not bundle multiple questions
- **Prefer multiple choice when possible** -- easier to process than open-ended
- If a topic needs more exploration, break it into sequential questions
- Focus on: purpose, constraints, success criteria, edge cases
- 4-6 questions is typical; stop when you have enough to propose approaches

### 3. Propose 2-3 Approaches

- Lead with your recommended option and explain why
- Be concrete about what each approach gives up and gains
- Keep each option description to 2-4 sentences

For each approach, include:
- **Name** (short, descriptive)
- **Summary** (2-3 sentences)
- **Key trade-off** (one sentence)
- **Effort** (Low / Medium / High)

### 4. Evaluate Approaches

Build a comparison matrix scoring each approach (1-5 scale):

| Criterion | Description |
|-----------|-------------|
| **Complexity** | How hard to implement (1=trivial, 5=very complex) |
| **Time** | How long to deliver (1=days, 5=months) |
| **Risk** | What could go wrong (1=safe, 5=high risk) |
| **Extensibility** | How well it scales/adapts (1=dead end, 5=very extensible) |
| **Alignment** | How well it fits existing architecture (1=foreign, 5=native) |

Provide an explicit recommendation with rationale and caveats.

### 5. Present the Design

- Present in sections scaled to complexity (a few sentences if straightforward, 200-300 words if nuanced)
- **Ask after each section whether it looks right** -- incremental validation
- Cover what's relevant: architecture, components, data flow, key decisions, error handling, testing
- Design for isolation: each unit should have one clear purpose, communicate through well-defined interfaces, and be testable independently
- Be ready to revise

### 6. Write the Design Document

After user approves, write the design to `docs/plans/YYYY-MM-DD-<topic>-design.md` and commit to git. The document should stand alone -- a reader without context should understand what's being built and why.

Include: goals, chosen approach (and why), design details, key decisions, out-of-scope items.

### 7. Spec Self-Review

After writing, review with fresh eyes:

1. **Placeholder scan** -- any TBD, TODO, incomplete sections, or vague requirements? Fix them.
2. **Internal consistency** -- do sections contradict each other? Does architecture match feature descriptions?
3. **Scope check** -- focused enough for a single implementation plan?
4. **Ambiguity check** -- could any requirement be interpreted two ways? Pick one and make it explicit.
5. **Re-work audit** -- if the design includes a phased implementation plan with ≥3 phases touching the same builder / sheet / module, walk each phase's concrete edits and tag every cell / formula / CF rule / function. If the same target appears in two phases (write-then-rewrite), pull the redesign forward into the layout-shift phase so every artifact lands in final form on first write. Phases after should be purely additive (new sections) or isolated (reorders, docs). Record the audit outcome as a numbered Decision in the plan's decisions log. *Why: splitting layout shifts from schema changes across phases silently writes the same formulas multiple times; a single mid-design "review ordering to minimize re-work" prompt can find 5-10 re-writes a naive phasing misses.*

Fix issues inline. Then ask the user to review the written spec before proceeding.

### 8. Transition to Implementation

Ask: "Ready to set up for implementation?" Then:
- Use `superpowers:using-git-worktrees` to create an isolated workspace
- Use `superpowers:writing-plans` to create a detailed implementation plan

---

## Deep Mode Process

Deep mode follows Quick mode's structure but inserts an **Ideation Phase** between Clarify (step 2) and Propose Approaches (step 3), and adds a **Deepen Phase** after evaluation.

### Steps 1-2: Same as Quick Mode

Understand context and clarify through questions.

### Step 2.5: Ideation Phase

After clarifying, select 1-3 techniques from the toolkit below. Apply them one at a time. Present results after each technique and ask if the user wants to continue exploring or move to convergence.

In Deep mode, ideation techniques can be dispatched in parallel as subagents.

#### Technique Selection Guide

Pick based on what the brainstorm needs:

| Situation | Technique |
|-----------|-----------|
| Need diverse viewpoints | Perspective Multiplication |
| Feeling stuck or conventional | Inversion |
| Want to improve something existing | SCAMPER Decomposition |
| Need creative leaps | Analogical Transfer |
| Working within hard limits | Constraint Variation |
| Uncertain about the future | Scenario Exploration |
| Want to stress-test assumptions | Assumption Challenge |

You don't need all of them. Pick the 1-3 that fit. Tell the user which technique you're using and why.

For the detailed playbook for each technique (steps, prompts, presentation tips), see `~/.claude/references/ideation-techniques-library.md`.

### Convergence

After ideation, synthesize the most promising ideas into 2-3 concrete approaches. Explicitly note which ideation insights shaped each approach. Then continue with steps 3-8 from Quick mode.

### Step 5.5: Deepen (Deep Mode Only)

After the user selects an approach from the evaluation matrix, go deeper:

**Abstraction Laddering** -- Analyze at three levels:
- Zoom OUT: what broader goal does this serve? Are we solving the right problem?
- Current level: the selected approach as stated
- Zoom IN: what are the concrete first 3 implementation steps?

**Hidden Assumptions** -- List 3-5 implicit assumptions. For each: "If we inverted this assumption, what would change?" Flag fragile assumptions.

**Pre-Mortem** -- Imagine the approach has FAILED. What went wrong?

| Failure Mode | Likelihood | Impact | Mitigation |
|-------------|:----------:|:------:|------------|
| [failure 1] | Med | High | [action] |
| [failure 2] | Low | High | [action] |
| [failure 3] | High | Med | [action] |

Incorporate mitigations into the final design. Then continue with steps 5-8.

---

## Anti-pattern reference

"This is too simple to need a design" and similar process-skipping rationalizations: see `~/.claude/references/anti-patterns-common-rationalizations.md`.
