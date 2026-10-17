"""
Crawl a business website and split its text into retrievable chunks.

Stays on the site's own domain, respects robots.txt and waits between
requests, so it is safe to point at a prospect's public site.
"""

import logging
import re
import time
from collections import Counter, deque
from urllib import robotparser
from urllib.parse import unquote, urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENT = "WebsiteAssistantDemoBot/1.0"
SKIP_EXTENSIONS = re.compile(
    r"\.(pdf|jpe?g|png|gif|svg|webp|ico|zip|mp3|mp4|mov|docx?|xlsx?|pptx?|css|js|xml|json)$",
    re.IGNORECASE,
)
# Pages visitors ask about most; crawled before the rest so a page cap never misses them.
PRIORITY_PATHS = re.compile(
    r"contact|about|location|find-us|visit|hours|faq|price|pricing|fees|admission|apply|"
    r"enrol|book|appointment|services|menu|team",
    re.IGNORECASE,
)
# Blogs, archives and listings rarely answer visitor questions; crawled only if budget remains.
LOW_VALUE_PATHS = re.compile(
    r"/(blog|news|article|articles|post|posts|tag|tags|category|categories|author|archive|events?)(/|$)"
    r"|/page/\d+|/\d{4}/\d{2}/",
    re.IGNORECASE,
)
NOISE_TAGS = ["script", "style", "noscript", "svg", "iframe", "form", "nav", "button", "template"]
TEXT_TAGS = [
    "h1", "h2", "h3", "h4", "h5", "p", "li", "td", "th", "dt", "dd",
    "address", "blockquote", "figcaption", "summary",
]
MIN_SECTION_CHARS = 300
# Below this, a page's text probably lives in <div>s (common on Wix/Webflow), so fall back to raw lines.
MIN_STRUCTURED_CHARS = 200
MAX_SITEMAP_URLS = 500


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _is_menu_item(el, text: str) -> bool:
    """A short list item that is nothing but a link is navigation, not content."""
    if el.name != "li" or len(text) > 60:
        return False
    link = el.find("a")
    return link is not None and " ".join(link.get_text(" ", strip=True).split()) == text


def extract_page(html: str, url: str) -> tuple[dict, list[str]]:
    """Return the page's readable text blocks, contact links and outgoing links."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    links = []
    contacts = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().startswith("tel:"):
            contacts.add("Phone: " + unquote(href[4:]).strip())
        elif href.lower().startswith("mailto:"):
            contacts.add("Email: " + unquote(href[7:]).split("?")[0].strip())
        elif "wa.me/" in href or "api.whatsapp.com" in href:
            contacts.add("WhatsApp: " + href)
        else:
            links.append(href)

    for tag in soup(NOISE_TAGS):
        tag.decompose()
    # "Behind Limitless Building<br>Al Khail Road" must not become "BuildingAl".
    for br in soup.find_all("br"):
        br.replace_with("\n")

    blocks = []
    root = soup.body or soup
    for el in root.find_all(TEXT_TAGS):
        # Skip containers whose text is captured by a nested block.
        if el.find(TEXT_TAGS):
            continue
        text = " ".join(el.get_text(" ", strip=True).split())
        if len(text) < 3 or _is_menu_item(el, text):
            continue
        blocks.append(f"## {text}" if el.name.startswith("h") else text)

    structured_chars = sum(len(b) for b in blocks)
    if structured_chars < MIN_STRUCTURED_CHARS:
        lines = [" ".join(line.split()) for line in root.get_text("\n").splitlines()]
        raw = [line for line in lines if len(line) >= 3]
        # Only when the tags clearly missed most of the text; a genuinely short page keeps its structure.
        raw_chars = sum(len(line) for line in raw)
        if structured_chars == 0 or raw_chars > max(2 * structured_chars, structured_chars + 150):
            blocks = raw

    page = {"url": url, "title": title or url, "blocks": blocks, "contacts": sorted(contacts)}
    return page, links


def chunk_page(page: dict, max_chars: int = 900) -> list[dict]:
    """Group a page's blocks into chunks of roughly max_chars, one block of overlap.

    A heading starts a new chunk only once the current one has real content,
    so runs of short sections ("Ranked 74th", "Our Results") stay together.
    """
    chunks = []
    current: list[str] = []
    section = ""

    def flush():
        body = "\n".join(b.removeprefix("## ") for b in current)
        if len(body) >= 40:
            chunks.append({
                "url": page["url"],
                "title": page["title"],
                "section": section,
                "text": body,
            })

    for block in page["blocks"]:
        size = sum(len(b) for b in current)
        if block.startswith("## ") and size >= MIN_SECTION_CHARS:
            flush()
            current = []
        if block.startswith("## ") and not current:
            section = block[3:]
        current.append(block)
        if size + len(block) >= max_chars:
            flush()
            current = current[-1:] if not current[-1].startswith("## ") else []

    if current:
        flush()
    return chunks


def contact_chunk(pages: list[dict], start_url: str) -> dict | None:
    """One chunk listing every phone, email and WhatsApp link found on the site."""
    # Site-wide details (the footer phone on every page) first; one-off ones (a caterer's email) last.
    counts = Counter(c for page in pages for c in page.get("contacts", []))
    if not counts:
        return None
    kind_order = {"Phone": 0, "WhatsApp": 1, "Email": 2}
    ranked = sorted(counts, key=lambda c: (-counts[c], kind_order.get(c.split(":")[0], 3), c))
    # "+971 (04) 423 8900" and "+97144238900" are one number written two ways (country code,
    # optional trunk 0). The last 8 digits identify it; keep the most common spelling.
    contacts, seen_numbers = [], set()
    for contact in ranked:
        if contact.startswith("Phone:"):
            tail = re.sub(r"\D", "", contact)[-8:]
            if tail in seen_numbers:
                continue
            seen_numbers.add(tail)
        contacts.append(contact)
    contact_pages = [p["url"] for p in pages if re.search(r"contact", p["url"], re.IGNORECASE)]
    return {
        "url": contact_pages[0] if contact_pages else start_url,
        "title": "Contact details",
        "section": "How to contact, call, email or reach us",
        "text": "\n".join(contacts),
    }


def sitemap_urls(client: httpx.Client, start_url: str, robots) -> list[str]:
    """Page URLs from the site's sitemap(s), following one level of sitemap index."""
    candidates = list((robots.site_maps() or []) if robots else []) or [urljoin(start_url, "/sitemap.xml")]
    found: list[str] = []
    for sitemap in candidates[:5]:
        try:
            response = client.get(sitemap)
        except httpx.HTTPError:
            continue
        if response.status_code != 200:
            continue
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", response.text)
        if "<sitemapindex" in response.text:
            candidates.extend(loc for loc in locs if loc not in candidates)
        else:
            found.extend(locs)
        if len(found) >= MAX_SITEMAP_URLS:
            break
    return found[:MAX_SITEMAP_URLS]


def crawl(start_url: str, max_pages: int = 40, delay: float = 0.5) -> list[dict]:
    """Crawl one site: contact/pricing/FAQ-type pages first, blogs and archives last."""
    if not start_url.startswith(("http://", "https://")):
        start_url = "https://" + start_url
    site_host = _host(start_url)

    robots = robotparser.RobotFileParser(urljoin(start_url, "/robots.txt"))
    try:
        robots.read()
    except Exception as e:  # unreachable robots.txt: crawl politely anyway
        logger.warning("Could not read robots.txt: %s", e)
        robots = None

    priority: deque[str] = deque()
    queue = deque([start_url])
    low: deque[str] = deque()
    queued = {start_url.rstrip("/")}
    seen_blocks: set[str] = set()
    pages = []

    def enqueue(link: str) -> None:
        key = link.rstrip("/")
        if (
            link.startswith(("http://", "https://"))
            and _host(link) == site_host
            and not SKIP_EXTENSIONS.search(link)
            and key not in queued
        ):
            queued.add(key)
            path = urlparse(link).path
            if LOW_VALUE_PATHS.search(path):
                low.append(link)
            elif PRIORITY_PATHS.search(path):
                priority.append(link)
            else:
                queue.append(link)

    with httpx.Client(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=15.0,
    ) as client:
        for link in sitemap_urls(client, start_url, robots):
            enqueue(urldefrag(link)[0])
        logger.info("Sitemap: %d pages queued", len(queued) - 1)

        while (priority or queue or low) and len(pages) < max_pages:
            url = (priority or queue or low).popleft()
            if robots and not robots.can_fetch(USER_AGENT, url):
                logger.info("robots.txt disallows %s", url)
                continue
            try:
                response = client.get(url)
            except httpx.HTTPError as e:
                logger.warning("Failed %s: %s", url, e)
                continue
            if response.status_code != 200 or "text/html" not in response.headers.get("content-type", ""):
                continue

            final_url = str(response.url)
            page, links = extract_page(response.text, final_url)
            # Drop text repeated on every page (menus, footers) after its first appearance.
            page["blocks"] = [b for b in page["blocks"] if not (b in seen_blocks or seen_blocks.add(b))]
            if page["blocks"] or page["contacts"]:
                pages.append(page)
                logger.info("[%d/%d] %s", len(pages), max_pages, final_url)

            for href in links:
                enqueue(urldefrag(urljoin(final_url, href))[0].split("?")[0])
            time.sleep(delay)

    return pages
