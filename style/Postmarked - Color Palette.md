# Postmarked Color Palette

This document records the current semantic token values from
`web/src/styles/global.css`. Use token names in application code, not raw hex
values, unless you are updating the token source itself.

## Dark Theme

Dark mode variables are defined as the fallback properties directly on `:root` in CSS. In practice, the application's resolved default is light mode unless the user's system theme is dark or they have explicitly selected dark mode.

| Token | Value | Use |
| --- | --- | --- |
| `--ink-0`, `--bg`, `--dark-page` | `#0D141C` | Page background |
| `--ink-1`, `--surface`, `--surface-1` | `#151D27` | Default surface |
| `--ink-2`, `--surface-2`, `--dark-card` | `#202A35` | Raised/nested surface |
| `--ink-3`, `--surface-3` | `#263241` | Strong nested surface |
| `--ink-4`, `--line`, `--dark-border` | `#3A4654` | Primary border |
| `--line-soft` | `#2B3542` | Subtle border |
| `--paper`, `--fg`, `--dark-paper-text` | `#F1E6C8` | Primary text |
| `--paper-2`, `--paper-muted` | `#D5C8AD` | Secondary text |
| `--muted`, `--dark-muted` | `#A7A091` | Metadata and quiet text |
| `--dim` | `#7B858E` | Placeholder and low-emphasis text |
| `--faint` | `#56616C` | Disabled/faint text |

## Light Theme

Light mode is selected with `:root[data-theme="light"]`.

| Token | Value | Use |
| --- | --- | --- |
| `--ink-0`, `--bg` | `#E1D7BE` | Page background |
| `--ink-1`, `--surface`, `--surface-1` | `#FBF4DF` | Default surface |
| `--ink-2`, `--surface-2` | `#E3D5B0` | Raised/nested surface |
| `--ink-3`, `--surface-3` | `#D5C7A8` | Strong nested surface |
| `--ink-4`, `--faint` | `#B9A98A` | Faint text and border-level primitive |
| `--line` | `#9A8A72` | Primary border |
| `--line-soft` | `#C0AE96` | Subtle border |
| `--paper`, `--fg` | `#111827` | Primary text |
| `--paper-2`, `--paper-muted` | `#2E2B28` | Secondary text |
| `--muted` | `#484340` | Metadata and quiet text |
| `--dim` | `#5B5652` | Placeholder and low-emphasis text |

## Brand And Accents

| Token | Dark | Light | Use |
| --- | --- | --- | --- |
| `--ember` | `#BD3325` | `#BD3325` | Brand, links, primary actions, active nav |
| `--ember-2` | `#D85643` | `#D85643` | Hover/secondary brand accent |
| `--ember-border` | `#8f3027` | `#8f3027` | Focus and primary button border |
| `--ember-glow` | `rgba(189, 51, 37, 0.16)` | `rgba(189, 51, 37, 0.16)` | Highlight background and glow |
| `--sky` | `#7AB8D6` | `#2C6F9D` | Info and unpublished state |
| `--forest` | `#6FA694` | `#3D7A6B` | Active/current/public/positive state |
| `--sunset` | `#EC8068` | `#D85643` | Private, warning, destructive-adjacent state |
| `--sage` | `#8AAE8D` | `#5E8E78` | Published/secondary positive state |
| `--postcard-yellow` | `#F0CB58` | `#C99A2C` | Special callout or needs-review accent |
| `--success` | `#4ade80` | `#2f9e54` | Success indicator and pulse dot |

## Specialized Tokens

| Token | Value | Use |
| --- | --- | --- |
| `--input-bg` | `var(--surface-2)` dark, `#f7efd8` light | Form fields |
| `--danger-border` | `color-mix(in srgb, var(--sunset) 45%, transparent)` | Destructive zones |
| `--cinema-bg` | `#05060a` | Media player page background |
| `--cinema-video-bg` | `#000` | Media player video well |

## Usage Rules

- Use semantic tokens in CSS and inline styles: `var(--ember)`, not `#BD3325`.
- Use Tailwind token utilities only when they are backed by `@theme` entries in
  `global.css`.
- Do not introduce page-local palettes.
- If a new color is needed more than once, add a token and document it here.
