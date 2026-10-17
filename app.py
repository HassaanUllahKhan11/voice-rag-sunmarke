"""
Website assistant server.

    /                     gallery of demo assistants + embed instructions
    /demo/<slug>          shareable demo page for one business (send this to a lead)
    /widget.js            embeddable chat widget
    /api/<slug>/info      business name, color, suggested questions
    /api/<slug>/ask       POST {"question", "history"} -> answer + sources
    /healthz              liveness check for the host
"""

import json
import logging
import os
import re
import time
from collections import defaultdict, deque
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, render_template, request
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from assistant.llm import answer
from assistant.search import SiteIndex

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("assistant.app")

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data" / "sites"
SLUG = re.compile(r"^[a-z0-9-]{1,60}$")
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")

MAX_QUESTION_CHARS = 500
MAX_HISTORY_ITEMS = 12
# Below this BM25 score the best passage is probably unrelated: no sources are shown and
# the question is logged as unanswered.
MIN_RELEVANT_SCORE = float(os.getenv("MIN_RELEVANT_SCORE", "5.0"))

# Per-IP limit so a public demo link can't drain the OpenRouter balance.
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_10_MIN", "30"))
RATE_WINDOW_SECONDS = 600
_requests: dict[str, deque] = defaultdict(deque)

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "static"))
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024
# Behind Vercel/Render the client IP arrives in X-Forwarded-For. ProxyFix trusts only the
# hops the platform adds, so a visitor can't dodge the rate limit by sending that header.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=int(os.getenv("TRUSTED_PROXY_HOPS", "1")), x_proto=1, x_host=1)


@lru_cache(maxsize=64)
def _load(slug: str, mtime: float) -> SiteIndex:
    return SiteIndex.load(DATA_DIR / f"{slug}.json")


def load_site(slug: str) -> SiteIndex:
    path = DATA_DIR / f"{slug}.json"
    if not SLUG.match(slug) or not path.is_file():
        abort(404, description=f"No assistant named '{slug}'")
    # Keyed on mtime, so re-running ingest.py is picked up without a restart.
    return _load(slug, path.stat().st_mtime)


def all_sites() -> list[dict]:
    return sorted(
        (load_site(p.stem).meta for p in DATA_DIR.glob("*.json") if SLUG.match(p.stem)),
        key=lambda m: m["name"].lower(),
    )


def on_accent(hex_color: str) -> str:
    """Near-black or white, whichever reads better on the business's brand color."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return "#ffffff"
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    luminance = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    # Contrast vs white is 1.05/(L+.05); vs #111 is (L+.05)/0.0556. Pick the larger.
    return "#ffffff" if 1.05 / (luminance + 0.05) >= (luminance + 0.05) / 0.0556 else "#111111"


def short_title(title: str) -> str:
    """'FAQs - Sunmarke School | British Curriculum' -> 'FAQs'."""
    first = re.split(r"\s[|–—-]\s", title)[0].strip()
    return first or title


def crawled_pages(site: SiteIndex) -> list[dict]:
    pages, seen = [], set()
    for chunk in site.chunks:
        if chunk["url"] in seen or chunk["title"] == "Contact details":
            continue
        seen.add(chunk["url"])
        path = chunk["url"].split("://", 1)[-1].split("/", 1)[-1].rstrip("/")
        pages.append({"title": short_title(chunk["title"]), "path": "/" + path if path else "/", "url": chunk["url"]})
    return pages


app.jinja_env.filters["on_accent"] = on_accent
app.jinja_env.filters["domain"] = lambda url: url.split("://", 1)[-1].removeprefix("www.").rstrip("/")


def owner_info() -> dict:
    """Who is offering the assistant; shown as the call to action."""
    return {
        "name": os.getenv("OWNER_NAME", ""),
        "email": os.getenv("OWNER_EMAIL", ""),
        "link": os.getenv("OWNER_BOOKING_LINK", ""),
    }


def rate_limited(ip: str) -> bool:
    now = time.monotonic()
    if len(_requests) > 10_000:  # drop idle visitors so memory stays bounded
        for stale in [k for k, w in _requests.items() if not w or now - w[-1] > RATE_WINDOW_SECONDS]:
            del _requests[stale]
    window = _requests[ip]
    while window and now - window[0] > RATE_WINDOW_SECONDS:
        window.popleft()
    if len(window) >= RATE_LIMIT:
        return True
    window.append(now)
    return False


def api_error(status: int, message: str):
    return jsonify({"error": message}), status


@app.after_request
def set_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    # The widget runs on clients' own domains, so the API must accept cross-origin calls.
    if request.path.startswith("/api/") or request.path == "/widget.js":
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Max-Age"] = "86400"
    return response


@app.get("/")
def index():
    return render_template(
        "index.html",
        sites=all_sites(),
        owner=owner_info(),
        host=request.host_url.rstrip("/"),
    )


@app.get("/demo/<slug>")
def demo(slug: str):
    site = load_site(slug)
    return render_template(
        "demo.html",
        site=site.meta,
        pages=crawled_pages(site),
        owner=owner_info(),
        host=request.host_url.rstrip("/"),
    )


@app.get("/widget.js")
def widget():
    response = app.send_static_file("widget.js")
    response.headers["Cache-Control"] = "public, max-age=300"
    return response


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True, "sites": len(list(DATA_DIR.glob("*.json")))})


@app.get("/api/<slug>/info")
def info(slug: str):
    meta = load_site(slug).meta
    return jsonify({**{k: meta[k] for k in ("name", "url", "color", "suggestions")}, "on_color": on_accent(meta["color"])})


@app.route("/api/<slug>/ask", methods=["POST", "OPTIONS"])
def ask(slug: str):
    if request.method == "OPTIONS":
        return "", 204
    site = load_site(slug)
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return api_error(400, "Send JSON like {\"question\": \"...\"}.")
    question = CONTROL_CHARS.sub("", str(body.get("question", ""))).strip()[:MAX_QUESTION_CHARS]
    if not question:
        return api_error(400, "Please type a question.")
    if rate_limited(request.remote_addr or "unknown"):
        return api_error(429, "Too many questions in a short time. Please try again in a few minutes.")

    history = body.get("history")
    history = history[-MAX_HISTORY_ITEMS:] if isinstance(history, list) else []

    passages = site.search(question, k=5)
    top_score = passages[0]["score"] if passages else 0.0
    relevant = top_score >= MIN_RELEVANT_SCORE
    if not relevant:
        # Unrelated passages only invite a confused answer; contact details let it hand off politely.
        passages = [c for c in site.chunks if c["title"] == "Contact details"]
    result = answer(site.meta, question, history, passages)

    sources, seen = [], set()
    if relevant:
        for p in passages[:3]:
            if p["url"] not in seen:
                seen.add(p["url"])
                sources.append({"title": p["title"], "url": p["url"]})

    # One JSON line per question: grep "unanswered" for questions the website doesn't cover.
    logger.info(json.dumps({
        "event": "question",
        "site": slug,
        "question": question[:200],
        "mode": result["mode"],
        "model": result["model"],
        "top_score": top_score,
        "unanswered": not relevant,
    }, ensure_ascii=False))
    return jsonify({**result, "sources": sources})


@app.errorhandler(HTTPException)
def http_error(error: HTTPException):
    if request.path.startswith("/api/"):
        messages = {413: "That message is too long.", 405: "Method not allowed."}
        return api_error(error.code or 500, messages.get(error.code, error.description))
    if error.code == 404:
        return render_template("404.html", message=error.description), 404
    return error


@app.errorhandler(Exception)
def server_error(error: Exception):
    logger.exception("Unhandled error on %s", request.path)
    if request.path.startswith("/api/"):
        return api_error(500, "Something went wrong on our side. Please try again.")
    return render_template("404.html", message="Something went wrong. Please try again."), 500


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG") == "1", port=int(os.getenv("PORT", "5000")))
