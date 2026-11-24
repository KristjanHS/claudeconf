# Spec-review re-work audit (mybrain step 7, check 6)

Loaded only when the design under review carries a phased implementation plan with ≥3 phases touching the same builder / sheet / module. Paste into the reviewer sub-agent's brief when the check fires.

Walk each phase's concrete edits and tag every cell / formula / CF rule / function.
If the same target appears in two phases (write-then-rewrite), pull the redesign forward into the layout-shift phase so every artifact lands in final form on first write.
Phases after should be purely additive (new sections) or isolated (reorders, docs).
Record the audit outcome as a numbered Decision in the plan's decisions log.

*Why: splitting layout shifts from schema changes across phases silently writes the same formulas multiple times; a single mid-design "review ordering to minimize re-work" prompt can find 5-10 re-writes a naive phasing misses.*
