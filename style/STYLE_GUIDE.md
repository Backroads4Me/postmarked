# Postmarked Style Guide

Postmarked uses one canonical stylesheet: `web/src/styles/global.css`.
Every future page, island, and component should start from the tokens and
classes in that file. Do not add a second theme stylesheet.

## Product Feel

Postmarked should feel like a polished travel journal with a practical admin
surface behind it: warm, legible, restrained, and easy to scan.

- Public pages should emphasize readable story content, clear location context,
  generous vertical rhythm, and restrained visual texture.
- Admin pages should be denser and work-focused, with predictable controls,
  compact tables, and clear status badges.
- Red is the brand/action color. Use it for primary actions, active nav, links,
  and focused states, not as a general decoration.
- Cards and controls should use an 8px radius or smaller.
- Avoid marketing-page patterns, oversized decorative sections, nested cards,
  gradient/orb backgrounds, and one-off page palettes.

## Source Of Truth

- Tokens, component classes, and utilities: `web/src/styles/global.css`
- Google Maps color constants: `web/src/lib/mapColors.js`
- Visual component lab: `web/src/pages/design-lab/postmarked-components.astro`
- Palette reference: `style/Postmarked - Color Palette.md`

If a page needs styling that is likely to recur, add or extend a shared class in
`global.css` instead of adding inline styles to the page.

## Typography

Use the type tokens, not font-family literals.

- Display headings: `.display` or `font-family: var(--display)`
- Body copy: `var(--body)`
- Pull quotes and italic emphasis: `var(--quote)`
- Labels, metadata, coordinates, badges: `var(--mono)`

`--sans` exists only as a backwards-compatible alias to `--body`. Do not use it
in new code.

Recommended text patterns:

- Page title: `.display` with a page-appropriate size.
- Section metadata: `.eyebrow`, `.label`, or `.coord`.
- Intro paragraph: `.lede`; add `.lede-body` when it should read as body copy.
- Long narrative body: `.prose-body`.
- Pull quote or public note: `.quote-block`.

## Layout

Use shared frames before custom max-width values.

- `.frame`: default page frame, 1200px max with responsive side padding.
- `.frame-narrow`: 1100px detail-page frame.
- `.frame-prose`: 720px single-column reading frame.

Public detail pages should usually be:

```astro
<Layout title="...">
  <main class="frame py-8 md:py-12">
    <div class="frame-narrow">
      ...
    </div>
  </main>
</Layout>
```

Post/article pages should use `.frame-prose` for the reading column. Admin
pages should favor `.frame` plus compact cards, lists, and tables.

## Surfaces

Use cards only for actual grouped UI, repeated items, and framed tools.
Do not put cards inside cards.

- `.card`: elevated interactive/repeated item. It has hover lift.
- `.card-flat`: quiet, non-hover grouped surface.
- `.card-hero`: important summary panel where a stronger treatment is needed.
- `.admin-list`: dense admin list/table shell.
- `.danger-zone`: destructive-action border, applied with `.card-flat`.

Keep page sections as normal layout bands or constrained content blocks, not
floating decorative cards.

## Buttons And Links

Use:

- `.btn` for secondary commands.
- `.btn-primary` for the main action on a page or form.
- `.btn-sm` for compact admin/table actions.
- `.btn-ghost` for low-emphasis actions.
- `.btn-ghost-ember` for low-emphasis brand actions.
- `.nav-link` for top and bottom navigation links.

Do not create page-local button padding, radius, font, or color rules unless the
control is genuinely unique.

## Forms

Use:

- `.form-input` for standard inputs, textareas, and selects.
- `.admin-input` for compact dense admin forms and table controls.

All form controls should have visible labels. Keep grouped form sections in
`.card-flat` unless the existing page has a stronger established pattern.

## Badges And Status

Use `.badge` plus a status modifier:

- `.badge-sm`: compact badge, including table rows and inline status.
- `.badge-active`: active/current/positive state.
- `.badge-draft`: draft/neutral state.
- `.badge-published`: published state.
- `.badge-unpublished`: unpublished/info state.
- `.badge-private`: private/warning/destructive-adjacent state.
- `.badge-public`: public/visible state.
- `.badge-ember`: brand-highlight state.

Do not use arbitrary `text-[9px]` or `text-[10px]` for badges. The known delete
button exception in `admin/stops/[trip_id].astro` is a button sizing choice, not
a badge pattern.

## Tables And Dense Admin UI

Use:

- `.table-header` for table headers.
- `.table-cell` for table cells.
- `.stop-picker-btn` for selectable stop rows.
- `.photo-item` and `.photo-item__name` for upload/media queue rows.

Prefer compact, readable layouts over spacious marketing-style composition in
admin screens.

## Maps

Map code has a separate source because Google Maps marker APIs cannot consume
CSS variables.

- CSS map tokens live in `global.css` as `--map-*`.
- JS map constants live in `web/src/lib/mapColors.js`.
- Keep both files aligned in the same change.

Use the JS constants for marker fill, route stroke, fallback map colors, and map
background colors.

## Media Player

The media player intentionally stays dark in both themes. Use:

- `--cinema-bg`
- `--cinema-video-bg`

Do not derive media-player chrome from the page theme unless the product
direction changes.

## Theme Behavior

Dark mode is the default. Light mode is selected with `data-theme="light"` on
`:root`.

Theme-sensitive CSS should use tokens rather than hardcoded color values. For
JS-driven theme behavior, keep theme-color meta values in sync with:

- Dark: `#0D141C`
- Light: `#E1D7BE`

## New Page Checklist

Before opening a PR for a new or restyled page:

- Uses `Layout.astro` or `AdminLayout.astro` as appropriate.
- Uses `.frame`, `.frame-narrow`, or `.frame-prose`; no page-local duplicate
  max-width values.
- Uses `.display`, `.lede`, `.prose-body`, `.eyebrow`, `.coord`, and `.label`
  where they fit.
- Uses `.card`, `.card-flat`, `.admin-list`, and shared button/form/badge
  classes before adding new CSS.
- Uses CSS variables for colors.
- Adds reusable styling to `global.css` when a pattern appears more than once.
- Checks both dark and light themes.
- Checks mobile width for overflow and text collisions.

## Drift Checks

Run the build:

```bash
cd web && npm run build
```

Then search for likely drift:

```bash
rg "text-\[9px\]|text-\[10px\]|font-family: var\(--sans\)|rgba\(212,107,92,\.45\)|max-width: 1100px|var\(--ok\)" web/src
```

Expected app hits should be rare and documented. As of the style
standardization, the intentional hits are `.frame-narrow` owning `1100px` and
the noted delete-button `text-[10px]` exception.
