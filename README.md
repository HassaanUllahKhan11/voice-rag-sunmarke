# Website AI Assistant

A voice-enabled RAG chat assistant for any business website. Point it at a site and it crawls the public pages, indexes them, and answers visitors' questions from that content only. It answers by text or voice and links to the page each answer came from. It installs on any site with one script tag.

Built as a sellable product for small businesses (clinics, schools, shops, agencies) and as a per-lead demo: crawl a prospect's site and send them a link to an assistant that already knows their business.

## Features

- **Crawler**: reads the sitemap, stays on the site's domain, respects `robots.txt` and rate-limits itself. It crawls contact/pricing/FAQ pages first and blogs and archives last, handles `<div>`-only page builders (Wix, Webflow), and collects phone numbers, emails and WhatsApp links into a contact passage ranked by how site-wide they are
- **Retrieval**: BM25 with title, heading and URL-path boosting, query expansion for common visitor questions ("where are you located" finds the address), a coverage bonus, and at most two passages per page. Pure Python with no model downloads, so it runs on free serverless hosting
- **Answers**: OpenRouter (Gemini 2.5 Flash by default, with an automatic fallback model) under a strict "only use the website" prompt. Off-topic questions get a polite hand-off with the business's contact details. With no key or credits it quotes the best-matching sentences, understanding label/value blocks and FAQ question/answer pairs, so a demo never breaks
- **Widget**: a shadow-DOM chat that can't clash with the host site's CSS, as a floating bubble or embedded inline. It has voice input and read-aloud (browser Web Speech API, no server cost), formatted answers, source links, a conversation that survives page navigation, readable text on any brand color, and a full-screen layout on phones
- **Demo pages**: `/demo/<slug>` is a personalised landing page for each prospect, showing the live assistant, the pages it read, and your call to action
- **Production basics**: proxy-aware per-IP rate limiting (can't be bypassed with a forged header), request size limits, JSON errors for every API failure, security headers, `/healthz`, one structured log line per question, a test suite and CI

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env            # then add OPENROUTER_API_KEY (optional for testing)

python ingest.py https://www.sunmarke.com --name "Sunmarke School" --color "#7c3aed"
python app.py
```

Open http://localhost:5000/demo/sunmarke-school.

### Build an assistant for a new business

```bash
python ingest.py https://www.example-dental.com --name "Example Dental" --color "#0e7490" --max-pages 40 \
  --suggest "Do you accept new patients?" --suggest "What are your opening hours?"
```

This writes `data/sites/example-dental.json`. Commit it and redeploy, and the demo is live at `/demo/example-dental`.

Sites that render their text with JavaScript (some Wix/React sites) return little content. The ingest script tells you when no pages could be read.

### Embed on a client's website

```html
<script src="https://YOUR-DEPLOYMENT/widget.js" data-site="example-dental" defer></script>
```

## Deploy

**Vercel**: import the repo, add `OPENROUTER_API_KEY` (and optionally `OWNER_NAME`, `OWNER_EMAIL`, `OWNER_BOOKING_LINK`) under Environment Variables, and deploy. `vercel.json` routes every request to the Flask app.

**Render**: New → Blueprint → select the repo. `render.yaml` configures the service. You'll be asked for the secret env vars.

## Unanswered questions

Every question is logged as one JSON line. Lines with `"unanswered": true` are what visitors asked that the website doesn't cover, which is useful to send a client as a monthly content report:

```bash
grep '"unanswered": true' logs.txt
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

CI runs the same on every push (`.github/workflows/tests.yml`).

## Configuration

| Variable | Purpose |
|---|---|
| `OPENROUTER_API_KEY` | Enables LLM answers. Without it, answers quote the best-matching passage |
| `OPENROUTER_MODEL` | Main model (default `google/gemini-2.5-flash`) |
| `OPENROUTER_FALLBACK_MODELS` | Comma-separated models tried if the main one fails |
| `OWNER_NAME`, `OWNER_EMAIL`, `OWNER_BOOKING_LINK` | Call to action on demo pages |
| `RATE_LIMIT_PER_10_MIN` | Questions per visitor IP per 10 minutes (default 30) |
| `TRUSTED_PROXY_HOPS` | Proxies that append to `X-Forwarded-For` (default 1, right for Vercel and Render) |
| `MIN_RELEVANT_SCORE` | Search score below which a question counts as not covered by the site (default 5.0) |

## Project layout

```
app.py              Flask server: demo pages, widget, JSON API
ingest.py           CLI: crawl a site -> data/sites/<slug>.json
assistant/crawl.py  polite same-domain crawler, text extraction, chunking
assistant/search.py BM25 index with query expansion
assistant/llm.py    OpenRouter answering with fallback + extractive mode
static/widget.js    embeddable chat widget (floating or inline, voice in/out)
tests/              pytest suite (crawler, search, LLM fallbacks, API)
templates/          demo, index and 404 pages
api/index.py        Vercel entry point
```

## API

- `GET /healthz` returns `{"ok": true, "sites": N}`
- `GET /api/<slug>/info` returns the business name, accent color and suggested questions
- `POST /api/<slug>/ask` takes `{"question": "...", "history": [{"role": "user"|"assistant", "content": "..."}]}` and returns `{"answer", "mode": "llm"|"extractive", "model", "sources": [{"title", "url"}]}`
