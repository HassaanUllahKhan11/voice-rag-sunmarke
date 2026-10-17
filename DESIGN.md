# Design

**World:** a prepared document, addressed to one business. Warm paper, ink type, one accent that belongs to the client (their brand color), never to us. Editorial, calm, confident; the live assistant is the hero, not illustration.

## Type

- Display: **Instrument Serif** (regular + italic), for headlines and numerals only.
- Text/UI: **Instrument Sans** 400/500/600.
- Scale: 13 / 15 / 17 / 20 / 28 / clamp(40px → 68px) display. Body 17px, line-height 1.55. Measure ≤ 62ch.

## Color tokens (`static/site.css`)

| Token | Light | Dark |
|---|---|---|
| `--paper` | #f4f1ea | #141311 |
| `--surface` | #fffdf8 | #1c1b18 |
| `--ink` | #1c1b18 | #eeeae1 |
| `--muted` | #67625a | #a39e93 |
| `--line` | #e1dbcd | #312e28 |
| `--accent` | per business (`meta.color`) | same |
| `--on-accent` | computed (#fff or #111) for contrast | same |

Accent is used for: primary button, chat user bubbles, links, small markers. Never for large backgrounds or body text.

## Components

- **Inline chat** (`widget.js` with `data-mode="inline"`): the hero of demo pages; bordered surface, no shadow theatrics.
- **Floating widget** (default mode): for client sites; system font by default, inherits `--assistant-font` when set.
- **Page index list:** numbered rows of crawled pages; proof the demo is personal.
- **Numbered reasons:** large serif numerals, no card grids.

## Bans

No card grids of icon+title+text, no gradients, no glassmorphism, no emoji, no stock illustration.
