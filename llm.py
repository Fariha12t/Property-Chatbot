"""OpenRouter client. Uses free models only, tries several in turn because free tiers are rate-limited."""
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
    return pinned or await _discover(client)


async def complete(messages: list[dict], max_attempts: int = 4) -> tuple[str, str]:
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
                    timeout=40,
                )
                if r.status_code != 200:
                    errors.append(f"{model}: HTTP {r.status_code}")
                    continue
                text = (r.json()["choices"][0]["message"].get("content") or "").strip()
                if text:
                    return text, model
                errors.append(f"{model}: empty reply")
            except Exception as e:  # timeouts, bad JSON, network
                errors.append(f"{model}: {type(e).__name__}")
    raise LLMUnavailable("; ".join(errors) or "no free models available")
