import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import llm
from .rag import Index, load_docs

ROOT = Path(__file__).resolve().parent.parent
index = Index(load_docs(ROOT / "data"))

app = FastAPI(title="DarGlobal and Wasalt assistant")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

SYSTEM = (
    "You are a helpful assistant for questions about two Saudi-linked real-estate companies: "
    "DarGlobal (luxury branded-residence developer) and Wasalt (Saudi property marketplace). "
    "Answer ONLY from the numbered context passages provided. Cite the passages you used like [1] or [2]. "
    "If the context does not contain the answer, say you don't have that information in the collected data "
    "and suggest checking the official site. Never invent prices, dates, or project details. "
    "Mention that listing prices and availability may have changed since the data was collected. "
    "Keep answers concise (under 180 words); use short bullet lists for comparisons."
)


class Turn(BaseModel):
    role: str
    content: str = Field(max_length=2000)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[Turn] = []


_hits: dict[str, deque] = defaultdict(deque)


def _rate_limit(request: Request, per_minute: int = 15) -> None:
    ip = (request.headers.get("x-forwarded-for") or request.client.host or "?").split(",")[0].strip()
    q, now = _hits[ip], time.time()
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= per_minute:
        raise HTTPException(429, "Too many requests. Please wait a minute and try again.")
    q.append(now)


@app.get("/health")
def health():
    return {"status": "ok", "chunks": index.stats()}


@app.post("/chat")
async def chat(body: ChatIn, request: Request):
    _rate_limit(request)
    users = [t.content for t in body.history if t.role == "user"]
    # Short follow-ups ("and in Riyadh?") borrow the previous question for retrieval.
    query = body.message if len(body.message.split()) > 5 or not users else f"{users[-1]} {body.message}"
    hits = index.search(query, k=8)
    sources = [{"n": i + 1, "title": h["title"], "url": h["url"], "site": h["site"]} for i, h in enumerate(hits)]

    if not hits:
        return {
            "answer": "I couldn't find anything about that in the DarGlobal or Wasalt data I have. "
            "Try asking about DarGlobal projects (e.g. Trump Tower Jeddah) or Wasalt listings and prices.",
            "sources": [],
            "model": None,
        }

    context = "\n\n".join(f"[{i + 1}] ({h['site']}) {h['title']}\n{h['text']}" for i, h in enumerate(hits))
    messages = [{"role": "system", "content": SYSTEM}]
    messages += [{"role": t.role, "content": t.content} for t in body.history[-6:] if t.role in ("user", "assistant")]
    messages.append({"role": "user", "content": f"Context:\n{context}\n\nQuestion: {body.message}"})

    try:
        answer, model = await llm.complete(messages)
        return {"answer": answer, "sources": sources, "model": model}
    except llm.LLMUnavailable:
        # Degrade gracefully: show the best-matching passages instead of failing.
        top = "\n\n".join(f"- {h['text'][:350].strip()}... [{i + 1}]" for i, h in enumerate(hits[:3]))
        return {
            "answer": "The language model is unavailable right now (free models are rate-limited), "
            f"so here are the most relevant passages I found:\n\n{top}",
            "sources": sources,
            "model": None,
        }


@app.get("/")
def home():
    return FileResponse(ROOT / "static" / "index.html")
