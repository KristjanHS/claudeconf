# Common Rationalizations & Process Anti-Patterns

Excuses people (and Claude) reach for when tempted to skip systematic debugging or design discipline. Read on demand whenever a process gate (systematic debugging, design review, test-first) is at risk of being skipped.

## Debugging Rationalizations

| Excuse | Reality |
|--------|---------|
| "Issue is simple, don't need process" | Simple issues have root causes too. Process is fast for simple bugs. |
| "Emergency, no time for process" | Systematic debugging is FASTER than guess-and-check thrashing. |
| "Just try this first, then investigate" | First fix sets the pattern. Do it right from the start. |
| "I'll write test after confirming fix works" | Untested fixes don't stick. Test first proves it. |
| "Multiple fixes at once saves time" | Can't isolate what worked. Causes new bugs. |
| "Reference too long, I'll adapt the pattern" | Partial understanding guarantees bugs. Read it completely. |
| "I see the problem, let me fix it" | Seeing symptoms ≠ understanding root cause. |
| "One more fix attempt" (after 2+ failures) | 3+ failures = architectural problem. Question pattern, don't fix again. |
| "Pre-existing noise, not from this change" | Tooling errors that survive across sessions are usually a 1-line config gap, not immutable. Investigate the resolver (pyrightconfig `extraPaths`, ruff target-version, etc.) before declaring it untouchable. |

## Design Anti-Pattern: "This Is Too Simple To Need A Design"

Every project goes through the design process. A config change, a one-page proposal, a simple script — all of them. "Simple" projects are where unexamined assumptions cause the most wasted work. The design can be short (a few sentences for truly simple projects), but present it and get approval.
