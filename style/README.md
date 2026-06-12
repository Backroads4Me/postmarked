# Postmarked Style Docs

This folder is the starting point for future UI work.

Postmarked has one implementation stylesheet: `web/src/styles/global.css`.
Do not create or import a second theme stylesheet. The historical
`postmarked-theme.css` override was removed because it duplicated tokens and
caused drift between layouts.

## Read Order

1. `STYLE_GUIDE.md` for page layout, component, typography, and implementation
   rules.
2. `web/src/styles/global.css` for current token values.

## Source Of Truth

- CSS tokens, utilities, and component classes: `web/src/styles/global.css`
- Google Maps color mirror: `web/src/lib/mapColors.js`
- UI examples: `web/src/pages/design-lab/postmarked-components.astro`

If these docs and code disagree, update the docs or `global.css` in the same
change. Do not work around mismatches with page-level inline styles.
