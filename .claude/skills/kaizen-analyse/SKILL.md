---
name: kaizen-analyse
description: Pick a Kaizen method (Gemba/Value Stream/Muda) for a target.
argument-hint: target (code, workflow, inefficiency)
---

# Smart Analysis

Auto-selects and applies the best Kaizen analysis technique for the target.

## Usage
`/analyse [target_description]`

## Method Selection Logic

**Gemba Walk** — analyzing code implementation, doc-vs-reality gaps, unfamiliar codebase areas
**Value Stream Mapping** — workflows, pipelines, bottlenecks, handoffs, cycle time
**Muda (Waste Analysis)** — over-engineering, duplication, technical debt, resource waste

## Steps
1. Understand what's being analyzed
2. Select method (or use user-specified method)
3. Explain why this method fits
4. Execute the analysis
5. Present findings with actionable recommendations

---

## Method 1: Gemba Walk

"Go and see" the actual code to understand reality vs. assumptions.

### Process
1. **Define scope**: What code area to explore
2. **State assumptions**: What you think it does
3. **Observe reality**: Read actual code
4. **Document findings**: Entry points, actual data flow, surprises, hidden dependencies, undocumented behavior
5. **Identify gaps**: Documentation vs. reality
6. **Recommend**: Update docs, refactor, or accept

---

## Method 2: Value Stream Mapping

Map workflow stages, measure time/waste, identify bottlenecks.

### Process
1. **Identify start and end**: Where process begins and ends
2. **Map all steps**: Including waiting/handoff time
3. **Measure each step**: Processing time, waiting time, owner
4. **Calculate metrics**: Total lead time, value-add vs. waste, % efficiency
5. **Identify bottlenecks**: Longest steps, most waiting
6. **Design future state**: Optimized flow
7. **Plan improvements**: How to get there

---

## Method 3: Muda (Waste Analysis)

Identify seven types of waste in code and processes.

### The 7 Wastes (Applied to Software)
1. **Overproduction**: Unused features, premature abstraction, unnecessary complexity
2. **Waiting**: Slow builds, review delays, blocked dependencies
3. **Transportation**: Unnecessary data transformations, redundant API layers
4. **Over-processing**: Redundant validation, excessive logging, over-normalized data
5. **Inventory**: Unmerged branches, half-finished features, untriaged bugs
6. **Motion**: Context switching, manual deployments, repetitive tasks
7. **Defects**: Production bugs, flaky tests, technical debt, incomplete features

### Process
1. **Define scope**: Codebase area or process
2. **Examine each waste type**: Look for concrete instances
3. **Quantify impact**: Time, complexity, or cost
4. **Prioritize by impact**
5. **Propose elimination strategies**

