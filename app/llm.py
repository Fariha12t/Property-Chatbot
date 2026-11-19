"""OpenRouter client. Free models only; remembers the model that works and skips ones that are failing."""
import os
import time

import httpx

BASE = "https://openrouter.ai/api/v1"
PREFERRED = ["gpt-oss", "llama-3.3", "gemma", "qwen", "mistral", "deepseek", "llama"]
STATIC_FALLBACK = [
    "openai/gpt-oss-20b:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
    "qwen/qwen3-14b:free",
]

_cache: dict = {"at": 0.0, "models": []}
_last_good: str | None = None
_cooldown: dict[str, float] = {}  # model -> time until which it is skipped


class LLMUnavailable(Exception):
    pass


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
        "HTTP-Referer": os.environ.get("APP_URL", "https://example.com"),
        "X-Title": "DarGlobal and Wasalt assistant",
    }


async def _discover(client: httpx.AsyncClient) -> list[str]:
    """Ask OpenRouter which models are currently free (availability changes often)."""
    if _cache["models"] and time.time() - _cache["at"] < 3600:
        return _cache["models"]
    try:
        r = await client.get(f"{BASE}/models", timeout=10)
        r.raise_for_status()
        free = []
        for m in r.json().get("data", []):
            p = m.get("pricing", {})
            outputs = (m.get("architecture") or {}).get("output_modalities") or ["text"]
            if str(p.get("prompt")) == "0" and str(p.get("completion")) == "0" and "text" in outputs:
                free.append(m)

        def rank(m):
            mid = m["id"].lower()
            pref = next((i for i, k in enumerate(PREFERRED) if k in mid), len(PREFERRED))
            return (pref, -(m.get("context_length") or 0))

        ids = [m["id"] for m in sorted(free, key=rank)]
        if ids:
            _cache.update(at=time.time(), models=ids)
            return ids
    except Exception:
        pass
    return STATIC_FALLBACK


async def candidates(client: httpx.AsyncClient) -> list[str]:
    pinned = [m.strip() for m in os.environ.get("OPENROUTER_MODELS", "").split(",") if m.strip()]
    models = pinned or await _discover(client)
    now = time.time()
    usable = [m for m in models if _cooldown.get(m, 0) <= now]
    if _last_good in usable:
        usable.remove(_last_good)
        usable.insert(0, _last_good)
    return usable or models


def _skip(model: str, seconds: int) -> None:
    _cooldown[model] = time.time() + seconds


async def complete(messages: list[dict], max_attempts: int = 8) -> tuple[str, str]:
    global _last_good
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise LLMUnavailable("OPENROUTER_API_KEY is not set")
    errors = []
    async with httpx.AsyncClient() as client:
        for model in (await candidates(client))[:max_attempts]:
            try:
                r = await client.post(
                    f"{BASE}/chat/completions",
                    headers=_headers(),
                    json={"model": model, "messages": messages, "temperature": 0.2, "max_tokens": 700},
                    timeout=25,
                )
                if r.status_code == 200:
                    text = (r.json()["choices"][0]["message"].get("content") or "").strip()
                    if text:
                        _last_good = model
                        return text, model
                    errors.append(f"{model}: empty reply")
                    _skip(model, 600)
                    continue
                errors.append(f"{model}: HTTP {r.status_code}")
                _skip(model, 60 if r.status_code == 429 else 3600)
            except Exception as e:  # timeouts, bad JSON, network
                errors.append(f"{model}: {type(e).__name__}")
                _skip(model, 120)
    print("LLM errors:", errors, flush=True)
    raise LLMUnavailable("; ".join(errors) or "no free models available")
