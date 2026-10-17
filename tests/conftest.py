import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from assistant.search import SiteIndex  # noqa: E402

CHUNKS = [
    {
        "url": "https://acme-dental.test/",
        "title": "Acme Dental | Family Dentist",
        "section": "Welcome",
        "text": "Acme Dental is a family dental clinic. We offer check-ups, teeth whitening and braces.",
    },
    {
        "url": "https://acme-dental.test/contact",
        "title": "Contact - Acme Dental",
        "section": "Visit us",
        "text": "Location\n12 High Street, Springfield\nOpening hours\nMonday to Friday, 9am to 6pm",
    },
    {
        "url": "https://acme-dental.test/prices",
        "title": "Prices - Acme Dental",
        "section": "Treatment prices",
        "text": "A check-up costs $60. Teeth whitening costs $250. Payment plans are available for braces.",
    },
    {
        "url": "https://acme-dental.test/faq",
        "title": "FAQ - Acme Dental",
        "section": "Questions",
        "text": "Do you accept new patients?\nYes, we are welcoming new patients of all ages.",
    },
    {
        "url": "https://acme-dental.test/contact",
        "title": "Contact details",
        "section": "How to contact, call, email or reach us",
        "text": "Phone: +1 555 0100\nEmail: hello@acme-dental.test",
    },
]

META = {
    "slug": "acme-dental",
    "name": "Acme Dental",
    "url": "https://acme-dental.test",
    "color": "#0e7490",
    "suggestions": ["Do you accept new patients?"],
    "pages": 4,
    "built": "2026-10-17",
}


@pytest.fixture
def site() -> SiteIndex:
    return SiteIndex(META, CHUNKS)


@pytest.fixture
def client(tmp_path, monkeypatch, site):
    """Flask test client serving one fixture site, with no LLM key (extractive mode)."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    import app as app_module

    data_dir = tmp_path / "sites"
    site.save(data_dir / "acme-dental.json")
    monkeypatch.setattr(app_module, "DATA_DIR", data_dir)
    app_module._load.cache_clear()
    app_module._requests.clear()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as test_client:
        yield test_client
