---
name: dev-ui-verify
description: Build or verify user-facing UI changes in the running app. Use for any change to how the UI looks or behaves — style, spacing, size, color, layout, components, interaction — including one-line CSS fixes (quick check). Not for text-only copy edits or backend-only work.
---

# UI Engineering and Browser Verification

A visual change is not complete from code inspection alone: shared styles, the cascade and responsive rules make CSS results hard to predict from the diff.

## Depth: match the check to the change

- **Small visual fix** (one component's spacing, size, color, alignment, a single style rule): start the app, open the affected screen, and capture one screenshot of the changed area. Add a mobile-width screenshot when the component is responsive. Glance for collateral changes in places that share the style. Skip the full checklist below.
- **Meaningful UI work** (new or reworked screens, layout or navigation changes, new interactions, responsive redesign): follow the whole procedure below.
- **Text-only copy edits** do not need this skill unless the new text can overflow, wrap or truncate.
- **The app cannot be run here** (no dev command, missing services): say the change is visually unverified and why. Never imply a visual check that did not happen.

## Before editing

1. Inspect the product's existing design system, tokens, shared components, and closest relevant screens.
2. Preserve existing information architecture and interaction contracts unless redesign is requested.
3. If a stronger visual direction is requested, use a small number of relevant references as evidence for hierarchy, density, navigation, and interaction patterns. Rebuild principles in the product's own language; do not copy branding or proprietary layouts.

## Production-quality defaults

Prefer content-first hierarchy, consistent spacing/type scales, semantic colors, clear primary/secondary actions, real loading/empty/error states where affected, responsive behavior designed with the change, and accessible native controls.

Avoid generic AI defaults unless the project already uses them: purple/indigo everywhere, gratuitous gradients, maximum-radius everything, uniform card grids that ignore priority, oversized equal padding, excessive shadows, generic hero layouts unrelated to content.

## Accessibility baseline

For affected interactions:
- use native semantic elements when available,
- preserve keyboard operation and visible focus,
- label controls without visible text,
- do not rely on color alone,
- maintain adequate contrast.

## Runtime verification

Start the actual application with verified project commands.
Check the changed route/state at a representative desktop viewport and mobile viewport, using project breakpoints when known.

Inspect where relevant:
- layout, density, spacing, alignment,
- typography and information hierarchy,
- overflow/clipping/wrapping,
- navigation and primary interactions,
- hover/focus/active states,
- loading, empty, and error states,
- browser console,
- failed network requests,
- responsive behavior.

Use screenshots when they materially help compare quality or prove the result.
If a visible issue is found, fix the underlying layout/style/interaction cause and rerun the affected browser check. Do not keep layering CSS exceptions over a wrong layout approach.

See `references/ui-quality.md` for a deeper review checklist.
