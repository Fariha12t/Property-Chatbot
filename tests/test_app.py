import os
from fastapi.testclient import TestClient
from app import llm
from app.main import app, index
from scraper.scrape import extract

c = TestClient(app)


def test_health_and_index():
    r = c.get("/health").json()
    assert r["status"] == "ok" and r["chunks"]["darglobal"] and r["chunks"]["wasalt"]


def test_retrieval_relevance():
    top = index.search("Tell me about Trump Tower Jeddah")[0]
    assert "Trump Tower Jeddah" in top["title"]
    top = index.search("villa in Taif 700,000 SAR")[0]
    assert "Taif" in top["title"]


def test_chat_fallback_without_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    j = c.post("/chat", json={"message": "What is Wasalt?"}).json()
    assert j["model"] is None and j["sources"] and "unavailable" in j["answer"]


def test_chat_with_mocked_llm(monkeypatch):
    async def fake(messages, max_attempts=4):
        assert "Context:" in messages[-1]["content"]
        return "Trump Tower Jeddah is a luxury tower [1].", "test/model:free"
    monkeypatch.setattr(llm, "complete", fake)
    j = c.post("/chat", json={"message": "What is Trump Tower Jeddah?", "history": []}).json()
    assert j["model"] == "test/model:free" and j["sources"][0]["n"] == 1


def test_no_hits():
    j = c.post("/chat", json={"message": "xyzzy qwerty"}).json()
    assert j["sources"] == []


def test_extract():
    html = "<html><head><title>T</title><meta name='description' content='desc here'></head><body><nav>menu</nav><main><h1>Villa</h1><p>" + "Spacious villa in Riyadh. " * 10 + "</p></main></body></html>"
    d = extract(html, "https://x/y")
    assert d["title"] == "T" and "Spacious villa" in d["text"] and "menu" not in d["text"]


def test_index_page():
    assert "DarGlobal and Wasalt assistant" in c.get("/").text
