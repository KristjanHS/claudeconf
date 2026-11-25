# Dataviz gotchas (pairs with the `dataviz` skill)

Non-obvious traps the `dataviz` skill's body doesn't spell out. The skill's bundled files live in a
version-scoped tmp path (regenerated per release), so durable dataviz facts are filed HERE.

## Categorical color on a scatter caps at ~3, not 4

The colorblind (CVD) floor for *categorical* hue on a **scatter** plot is ~3 distinguishable series —
adding a 4th CVD-independent tint does NOT clear the floor (points are small, low-area marks; hue
separation that works on filled bars/areas fails on scattered dots). Don't try to encode a 2×2 (4
categories) as 4 scatter colors.

**When one axis of the category is already encoded, spend the added channel on the FREE axis only —
don't re-encode the whole 2×2.** E.g. if the x/y position already carries one factor of a 2×2, the
color/shape channel should carry just the *other* factor (2 levels), not all four combinations. Re-
encoding the already-positioned axis wastes the channel and pushes past the categorical-on-scatter cap.
(private-app 2026-07-22: a 2×2 overlay tried 4 CVD tints on a scatter; the fix was to color by the one
un-positioned axis.)
