# Product

**What:** A website AI assistant for small businesses. It crawls a business's public site and answers visitors' questions from that content, by text or voice, citing the source pages. It installs with one script tag.

**Who builds and sells it:** Hassaan Ullah Khan, a freelance data/AI engineer (Islamabad), selling to small businesses (clinics, schools, shops, agencies), mostly international, outside Upwork/Fiverr.

**How it's sold:** Cold outreach with a personalized demo link (`/demo/<slug>`) built from the prospect's own website. The demo page must convince a busy, non-technical owner within seconds that (1) this already knows *their* business and (2) it's worth a call.

## Surfaces

| Surface | Mode | Visitor's success |
|---|---|---|
| `/demo/<slug>` | Persuade | Tries the assistant, sees it's about them, books a call / replies |
| `/` | Persuade | Understands the offer, opens a demo |
| `widget.js` | Operate | Gets a correct answer fast on a client's site; must blend into any host site |

## Constraints

- Each business has its own accent color (`meta.color`); the page and widget must stay legible with any color.
- No claims about the business beyond its own website; demo pages say "not affiliated".
- Free-tier hosting (Vercel/Render): no build step, no heavy JS.
