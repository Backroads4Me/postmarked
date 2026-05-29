# Postmarked — Style Standardization Plan & Progress

> Living checklist. Each item is checked off as it is completed so work is
> resumable. See `style/STYLE_GUIDE.md` for the resulting canonical guide.

## Context

Postmarked's UI styling drifted because **two competing theme stylesheets** were
both imported (`Layout.astro` + `AdminLayout.astro`):

- `web/src/styles/global.css` — structure (Tailwind v4 `@theme`, `@layer
  base/utilities/components`, ~60 classes) but the **legacy goodpath palette**
  (orange `--ember: #e8893f`, Inter `--sans`).
- `web/src/styles/postmarked-theme.css` — imported **second**, overriding nearly
  every color/font with the **current postmarked brand** (red `--ember: #BD3325`,
  cream paper, Playfair / Source Serif 4 / IBM Plex Mono) and redefining badges.

Three peer reviews (`review-1/2/3.md`) additionally found hardcoded hex in
map/island components, inline styles duplicating existing classes, selects
skipping `.form-input`, ad-hoc badge sizing (`text-[9px]`), repeated inline
containers/`.lede` overrides, hardcoded danger borders, and undefined tokens
(`--ok`, `--ember-border`/`--input-bg`).

**Confirmed decisions:** (1) standardize on red/cream + serif (postmarked);
(2) full standardization incl. islands/maps; (3) add `--body` token, keep `--sans`
as alias; (4) shared `mapColors.js` module for Google-Maps colors.

---

## Phase 1 — Consolidate to a single CSS source of truth (`global.css`)

- [x] 1.1 Move the three `@font-face` blocks into `global.css` (after `@import`)
- [x] 1.2 Replace `:root` dark hex values with postmarked palette (ink scale,
      line, paper, ember red, accents, `--dark-*`, `--ember-border`, nav/shadow)
- [x] 1.3 Add typography tokens (`--font-display/body/label`, `--display`,
      `--quote`, `--body` NEW, `--sans` alias→`--body`, `--mono`)
- [x] 1.4 Add new semantic tokens: `--ok`/`--success`, `--input-bg`,
      `--danger-border`, `--cinema-bg`/`--cinema-video-bg`, `--map-*`
- [x] 1.5 Replace `:root[data-theme="light"]` with postmarked light values +
      light counterparts for new tokens
- [x] 1.6 `@theme`: status colors → `var()`; add `--color-ember-border`,
      `--color-postcard-yellow`, `--color-success`, `--color-danger`, `--font-body`
- [x] 1.7 Fold corrected badge values into `global.css`, remove duplicates
- [x] 1.8 Migrate `.admin-input`/`.admin-list` from `AdminLayout.astro` into `global.css`
- [x] 1.9 Delete `postmarked-theme.css`; remove its import from both layouts;
      move `.lede em`/`.quote` rule into `global.css`

## Phase 2 — New reusable classes (in `global.css`)

- [x] 2.1 `.frame-narrow` (1100px) and `.frame-prose` (720px)
- [x] 2.2 `.badge-sm` (owns badge font-size; replaces `text-[9px]`/`text-[10px]`)
- [x] 2.3 `.lede-body` (serif body font override for `.lede`)
- [x] 2.4 `.prose-body` (body font, line-height 1.7, pre-wrap)
- [x] 2.5 `.quote-block` (from inline blockquote)
- [x] 2.6 `.danger-zone` (uses `--danger-border`)
- [x] 2.7 `.stop-picker-btn`; `.table-header`/`.table-cell`; `.photo-item`

## Phase 3 — Apply classes across pages (`.astro`)

- [x] 3.1 Selects → `.form-input` / `.admin-input` (`admin/posts/[id].astro`,
      `admin/stops/[trip_id].astro`)
- [x] 3.2 Badges: `text-[9px]`/`text-[10px]` → `badge-sm` (trips, admin pages).
      Note: delete-button `text-[10px]` in `admin/stops/[trip_id].astro:229`
      left as-is (button size, not a badge).
- [x] 3.3 `.lede` inline sans → `.lede lede-body`; inline body paras → `.prose-body`
- [x] 3.4 Inline `max-width` containers → `.frame-narrow` / `.frame-prose`
- [x] 3.5 Blockquote → `.quote-block`
- [x] 3.6 Danger zones → `.card-flat danger-zone` (trips/[id], stop_id, media/index)
- [x] 3.7 `media-player/[id].astro` → `--cinema-bg` / `--cinema-video-bg`
- [x] 3.8 theme-color meta sync (Layout, AdminLayout, ThemeToggle) → `#0D141C`/`#E1D7BE`

## Phase 4 — JS island & map refactors

- [x] 4.1 Create `web/src/lib/mapColors.js`; refactor `StopMapIsland.jsx` +
      `MapIsland.jsx` (incl. fallback orange → ember red)
- [x] 4.2 `ImportPreviewIsland.jsx`: `statusColor()` → tokens; inline badges →
      `.badge-*`; `thStyle`/`tdStyle` → classes
- [x] 4.3 `QuickPostIsland.jsx`: `var(--ok)` → `var(--success)`; `inputStyle` →
      `.form-input`; photo rows → classes
- [x] 4.4 `CurrentStopPickerIsland.jsx` → `.stop-picker-btn`
- [x] 4.5 `SearchIsland.jsx:56` → `.nav-link`; `global.css` pulse-dot → `var(--success)`

## Phase 5 — Docs

- [x] 5.1 Write `STYLE_GUIDE.md` (canonical guide)
- [x] 5.2 This plan kept in repo and checked off

## Verification

- [x] V1 `cd web && npm run build` succeeds
- [ ] V2 Visual pass both themes (home, trips, stop, post, admin, maps, player)
- [x] V3 Drift grep returns ~0 (`text-[9px]`, `text-[10px]`,
      `font-family: var(--sans)`, `rgba(212,107,92,.45)`, `max-width: 1100px`,
      `var(--ok`)
      Remaining app hits are intentional: `.frame-narrow` owns 1100px and the
      delete button noted above keeps `text-[10px]`.
- [ ] V4 `design-lab/postmarked-components.astro` renders correctly
