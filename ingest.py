"""
Build a website assistant for one business.

    python ingest.py https://www.example-clinic.com --name "Example Clinic"

Crawls the site, chunks its text and writes data/sites/<slug>.json, which
the app serves at /demo/<slug>.
"""

import argparse
import logging
import re
from datetime import date
from pathlib import Path

from assistant.crawl import chunk_page, contact_chunk, crawl
from assistant.search import SiteIndex

DATA_DIR = Path(__file__).parent / "data" / "sites"

DEFAULT_SUGGESTIONS = [
    "What services do you offer?",
    "Where are you located?",
    "How can I contact you?",
    "What are your opening hours?",
]


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url", help="Business homepage, e.g. https://www.example.com")
    parser.add_argument("--name", required=True, help="Business name shown in the assistant")
    parser.add_argument("--slug", help="URL-safe id (default: from --name)")
    parser.add_argument("--max-pages", type=int, default=40)
    parser.add_argument("--color", default="#2563eb", help="Accent color for the widget")
    parser.add_argument(
        "--suggest",
        action="append",
        help="Suggested question shown to visitors (repeatable)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    slug = args.slug or slugify(args.name)

    pages = crawl(args.url, max_pages=args.max_pages)
    if not pages:
        raise SystemExit(
            "No pages could be read. The site may block bots or render its text with JavaScript."
        )

    total_chars = sum(len(b) for page in pages for b in page["blocks"])
    if total_chars < 1500:
        logging.warning(
            "Only %d characters of text found across %d pages. The site probably renders its content "
            "with JavaScript; answers will be thin. Consider a richer page list or a manual FAQ.",
            total_chars, len(pages),
        )

    chunks = [chunk for page in pages for chunk in chunk_page(page)]
    contacts = contact_chunk(pages, args.url)
    if contacts:
        chunks.append(contacts)
    meta = {
        "slug": slug,
        "name": args.name,
        "url": args.url,
        "color": args.color,
        "suggestions": args.suggest or DEFAULT_SUGGESTIONS,
        "pages": len(pages),
        "built": date.today().isoformat(),
    }
    path = DATA_DIR / f"{slug}.json"
    SiteIndex(meta, chunks).save(path)
    print(f"\nIndexed {len(pages)} pages into {len(chunks)} chunks -> {path}")
    print(f"Demo: http://localhost:5000/demo/{slug}")


if __name__ == "__main__":
    main()
