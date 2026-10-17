import app as app_module


def ask(client, question, **extra):
    return client.post("/api/acme-dental/ask", json={"question": question, **extra})


def test_info_includes_readable_text_color(client):
    data = client.get("/api/acme-dental/info").get_json()
    assert data["name"] == "Acme Dental"
    assert data["on_color"] == "#ffffff"


def test_ask_returns_answer_and_sources(client):
    response = ask(client, "How much does teeth whitening cost?")
    data = response.get_json()
    assert response.status_code == 200
    assert data["mode"] == "extractive"
    assert "$250" in data["answer"]
    assert data["sources"][0]["url"].endswith("/prices")
    assert response.headers["Access-Control-Allow-Origin"] == "*"


def test_unrelated_question_gets_contact_handoff_and_no_sources(client):
    data = ask(client, "What is the capital of France?").get_json()
    assert data["sources"] == []
    assert "Phone: +1 555 0100" in data["answer"]


def test_bad_requests_get_json_errors(client):
    assert ask(client, "   ").status_code == 400
    assert client.post("/api/acme-dental/ask", data="not json", content_type="application/json").status_code == 400
    assert client.post("/api/acme-dental/ask", json=["a list"]).status_code == 400
    too_big = client.post("/api/acme-dental/ask", json={"question": "x" * 40_000})
    assert too_big.status_code == 413 and "error" in too_big.get_json()
    missing = client.post("/api/nope/ask", json={"question": "hi"})
    assert missing.status_code == 404 and "error" in missing.get_json()
    assert client.get("/api/acme-dental/ask").status_code == 405


def test_rate_limit_uses_proxy_ip_not_spoofable_header(client, monkeypatch):
    monkeypatch.setattr(app_module, "RATE_LIMIT", 2)
    headers = {"X-Forwarded-For": "1.1.1.1"}
    assert ask(client, "hours", headers=headers).status_code == 200
    assert ask(client, "hours", headers=headers).status_code == 200
    assert ask(client, "hours", headers=headers).status_code == 429
    # Prepending a fake address doesn't reset the limit: only the proxy-added hop is trusted.
    spoofed = {"X-Forwarded-For": "9.9.9.9, 1.1.1.1"}
    assert ask(client, "hours", headers=spoofed).status_code == 429


def test_pages_render(client):
    demo = client.get("/demo/acme-dental")
    assert demo.status_code == 200
    html = demo.get_data(as_text=True)
    assert "Acme Dental" in html and "acme-dental.test" in html
    assert 'data-mode="inline"' in html
    assert demo.headers["X-Content-Type-Options"] == "nosniff"

    assert "Acme Dental" in client.get("/").get_data(as_text=True)
    assert client.get("/demo/missing").status_code == 404
    assert client.get("/healthz").get_json() == {"ok": True, "sites": 1}
    assert client.get("/widget.js").status_code == 200


def test_on_accent_picks_readable_text():
    assert app_module.on_accent("#facc15") == "#111111"  # yellow
    assert app_module.on_accent("#1e3a8a") == "#ffffff"  # navy
    assert app_module.on_accent("not-a-color") == "#ffffff"


def test_short_title():
    assert app_module.short_title("FAQs - Sunmarke School | British Curriculum") == "FAQs"
    assert app_module.short_title("Plain") == "Plain"
