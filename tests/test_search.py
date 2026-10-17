from assistant.search import SiteIndex, best_sentences, expand_query, tokenize


def test_tokenize_stems_and_drops_stopwords():
    assert tokenize("Where are you located?") == ["locat"]
    assert tokenize("locations") == tokenize("location")


def test_query_expansion_bridges_vocabulary():
    weights = expand_query("Where are you located?")
    assert weights[tokenize("located")[0]] == 1.0
    assert weights[tokenize("address")[0]] == 0.5


def test_search_finds_right_page(site):
    assert site.search("How much does whitening cost?")[0]["url"].endswith("/prices")
    assert site.search("What are your opening hours?")[0]["url"].endswith("/contact")
    assert site.search("Do you take new patients?")[0]["url"].endswith("/faq")


def test_search_limits_chunks_per_page():
    chunks = [{"url": "https://a.test/same", "title": "Fees", "section": "", "text": f"fees fees {i}"} for i in range(5)]
    chunks.append({"url": "https://a.test/other", "title": "Other", "section": "", "text": "fees"})
    results = SiteIndex({}, chunks).search("fees", k=5, per_page=2)
    assert [r["url"] for r in results].count("https://a.test/same") == 2
    assert results[-1]["url"] == "https://a.test/other"


def test_search_returns_nothing_for_unrelated_query(site):
    assert site.search("capital of France") == []


def test_best_sentences_handles_label_and_faq_pairs(site):
    location = best_sentences("Where are you located?", site.search("Where are you located?"))
    assert "Location: 12 High Street, Springfield" in location

    faq = best_sentences("Do you accept new patients?", site.search("Do you accept new patients?"))
    assert faq[0] == "Yes, we are welcoming new patients of all ages."


def test_save_and_load_round_trip(tmp_path, site):
    path = tmp_path / "site.json"
    site.save(path)
    loaded = SiteIndex.load(path)
    assert loaded.meta == site.meta
    assert loaded.search("whitening")[0]["url"] == site.search("whitening")[0]["url"]
