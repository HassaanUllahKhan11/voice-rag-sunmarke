from assistant.crawl import chunk_page, contact_chunk, extract_page

HTML = """
<html><head><title>Contact - Acme Dental</title></head>
<body>
  <nav><a href="/">Home</a></nav>
  <ul><li><a href="/prices">Prices</a></li></ul>
  <h1>Visit us</h1>
  <p>12 High Street<br>Springfield</p>
  <p>Call <a href="tel:+15550100">+1 555 0100</a> or
     <a href="mailto:hello@acme-dental.test?subject=Hi">email us</a>.</p>
  <a href="https://wa.me/15550100">WhatsApp</a>
  <script>var tracking = 1;</script>
</body></html>
"""


def test_extract_page_text_contacts_and_links():
    page, links = extract_page(HTML, "https://acme-dental.test/contact")

    assert page["title"] == "Contact - Acme Dental"
    assert "## Visit us" in page["blocks"]
    # <br> becomes a space, not a glued word.
    assert "12 High Street Springfield" in page["blocks"]
    # Menu-only list items and scripts are dropped.
    assert not any("Prices" == b for b in page["blocks"])
    assert not any("tracking" in b for b in page["blocks"])
    assert page["contacts"] == [
        "Email: hello@acme-dental.test",
        "Phone: +15550100",
        "WhatsApp: https://wa.me/15550100",
    ]
    assert "/prices" in links


def test_div_only_pages_fall_back_to_raw_lines():
    html = "<html><body><div>Open every day</div><div>We repair bikes of every brand and size.</div></body></html>"
    page, _ = extract_page(html, "https://bikes.test/")
    assert "We repair bikes of every brand and size." in page["blocks"]


def test_chunk_page_merges_short_sections_and_caps_size():
    blocks = ["## Intro", "Short line one.", "## Tiny", "Short line two."] + [f"Sentence number {i} " * 6 for i in range(20)]
    chunks = chunk_page({"url": "u", "title": "t", "blocks": blocks}, max_chars=400)

    # The two short sections share a chunk instead of producing one-line fragments.
    assert "Short line one." in chunks[0]["text"] and "Short line two." in chunks[0]["text"]
    assert all(len(c["text"]) < 400 + 200 for c in chunks)
    assert chunks[0]["section"] == "Intro"


def test_contact_chunk_ranks_site_wide_details_first():
    pages = [
        {"url": "https://x.test/", "contacts": ["Phone: 1", "Email: main@x.test"]},
        {"url": "https://x.test/contact", "contacts": ["Phone: 1", "Email: caterer@x.test"]},
    ]
    chunk = contact_chunk(pages, "https://x.test/")
    assert chunk["url"] == "https://x.test/contact"
    assert chunk["text"].splitlines()[0] == "Phone: 1"
    assert contact_chunk([{"url": "u", "contacts": []}], "u") is None


def test_contact_chunk_merges_one_number_written_two_ways():
    pages = [
        {"url": "https://x.test/", "contacts": ["Phone: +971 (04) 423 8900"]},
        {"url": "https://x.test/a", "contacts": ["Phone: +971 (04) 423 8900", "Phone: +97144238900"]},
    ]
    assert contact_chunk(pages, "https://x.test/")["text"] == "Phone: +971 (04) 423 8900"
