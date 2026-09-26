# Ideation Techniques Library

Detailed toolkit for the `mybrain` skill's Deep mode Ideation Phase. Loaded on demand via the technique-selection guide in `~/.claude/skills/mybrain/SKILL.md` § Deep Mode Process.

Pick 1–3 techniques per ideation round; don't run all of them.

## Technique selection guide

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

## Perspective Multiplication

Generate ideas from 3–5 relevant viewpoints for the domain:
- Stakeholder roles (end user, admin, support team, executive, regulator)
- Expertise angles (security engineer, UX designer, data scientist, ops)
- Contrarian perspectives ("what would a competitor do?", "what would a startup with zero legacy do?")

For each, generate 2–3 ideas or concerns. Present a consolidated view showing where perspectives align and conflict.

## Inversion (Reverse Brainstorming)

Instead of "how do we solve X?", ask "how could we make X as bad as possible?"

1. Generate 5–8 ways to make the problem worse
2. Flip each into a concrete positive solution
3. The best inversions reveal blind spots that direct thinking misses

Present the worst ideas first (often funny and energizing), then show the flipped solutions.

## SCAMPER Decomposition

Apply structured transformations to an existing concept:
- **S**ubstitute — what components could be replaced?
- **C**ombine — what could be merged for simplicity or new capability?
- **A**dapt — what could be borrowed from other domains?
- **M**odify — what could be enlarged, shrunk, or changed in emphasis?
- **P**ut to other use — what else could this serve?
- **E**liminate — what's unnecessary? What happens if you remove it?
- **R**everse/Rearrange — what if the order or structure changed?

Don't force all seven. Pick the 2–4 most relevant and go deep.

## Analogical Transfer

Find parallels from different domains:

1. Identify the core challenge abstractly (e.g., "routing limited resources under uncertainty")
2. Find 2–3 domains that solve structurally similar problems (e.g., logistics, biology, game theory)
3. Extract the principles that make those solutions work
4. Map those principles back to the user's specific context

The value is in surprising connections that break conventional thinking.

## Constraint Variation

Explore how the solution changes when you tighten or relax constraints:
- "What if the budget were 10x smaller? 10x larger?"
- "What if you had to ship in 1 week? What if you had a year?"
- "What if the primary user were a complete novice? An expert?"
- "What if this had to work offline? In 50 countries?"

Pick 2–3 constraint shifts most revealing for the problem.

## Scenario Exploration

Explore 2–3 plausible futures and design for resilience:
- Best case: everything goes right — what does success look like?
- Worst case: key assumptions fail — what breaks first?
- Wildcard: unexpected change (new regulation, competitor move, tech shift) — how does the design hold up?

## Assumption Challenge

List 5–8 assumptions embedded in the current framing. For each:

1. State the assumption explicitly
2. Is this actually true? What evidence supports it?
3. What would change if this assumption were wrong?

The most productive challenges are assumptions the user didn't realize they were making.

---

## Deepen phase (after an approach is selected)

`mybrain` Deep mode step 5.5 — run all three, then fold mitigations into the final design and continue with steps 5-8. Unlike the divergent techniques above, these three run together on the *already-chosen* approach.

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
