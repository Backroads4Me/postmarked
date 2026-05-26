# Postmarked Theme Implementation Plan

## Summary
Adopt the "Greetings From" theme direction from `/home/ted/Downloads/postmarked-theme.css` by implementing the palette, badge retuning, quote utility, and self-hosted font setup. Keep the current brand mark.

## Review Notes
- The palette is implemented as a token override so existing components can pick up the new theme without layout changes.
- The provided red "P" brand mark override is intentionally excluded.
- Fonts are self-hosted from local `/fonts/` assets rather than loaded from Google at runtime.
- The `--paper-muted` compatibility alias is defined by the theme to cover existing component usage.

## Implementation
- Add `web/src/styles/postmarked-theme.css` and import it after `global.css` in both public and admin layouts.
- Add self-hosted WOFF2 assets under `web/public/fonts/`.
- Define `@font-face` declarations for DM Serif Display, Newsreader, Inter, and JetBrains Mono.
- Apply dark and light "Greetings From" token overrides, plus badge retuning and `.quote` / `.lede em` styling.
- Preserve the existing CSS-built brand mark.

## Verification
- Run `npm run build` in the web container.
- Check dark and light themes on the homepage, stop detail page, post detail page, admin posts page, and admin backup page.
- Confirm font requests are local `/fonts/...` URLs.
- Confirm badges remain legible in both themes.
