# UI Quality Reference

Load this reference only when the active UI task needs deeper visual review.

## Hierarchy
- Make the screen's primary job visually obvious.
- Secondary controls should not compete with the primary workflow.
- Group information by user task and scanning pattern, not implementation module.

## Density
- Data-heavy and financial products often need more information density than marketing sites.
- Dense does not mean cramped: rely on alignment, grouping, consistent row heights, and progressive detail.
- Avoid turning every metric into an independent decorative card.

## Responsive behavior
- Preserve priority as width shrinks.
- Collapse secondary detail before primary actions.
- Prefer deliberate reflow over accidental clipping.
- Tables need an intentional mobile strategy: selective columns, grouped rows, drill-down, or controlled horizontal scrolling.

## State quality
Exercise realistic loading, partial data, empty data, error, stale/retry states when the change can affect them.

## Interaction quality
- Controls should look interactive before hover.
- Hover cannot be the only affordance.
- Keyboard focus remains visible.
- Disabled controls explain why when the reason is not obvious.
