---
title: DarGlobal and Wasalt Assistant
emoji: 🏙️
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# DarGlobal and Wasalt assistant

A retrieval-augmented chatbot that answers questions about **DarGlobal** (luxury branded-residence developer) and **Wasalt** (Saudi property marketplace), using data scraped from their public websites and a **free OpenRouter model**. Containerised with Docker and deployable to a public URL.

```
scraper/scrape.py  ->  data/scraped/*.jsonl ─┐
data/seed/*.jsonl (starter dataset) ─────────┴->  BM25 index  ->  FastAPI /chat  ->  OpenRouter free model  ->  answer + sources
```

## How it works
- **Scraping** (`scraper/scrape.py`): reads each site's `robots.txt` and sitemap, falls back to link crawling, extracts page text (plus JSON-LD / Next.js embedded data for JS-heavy pages), waits between requests, and skips anything robots.txt disallows. Wasalt has a huge number of listings, so it takes all non-listing pages plus a sample of listings.
- **Retrieval** (`app/rag.py`): chunking plus BM25, implemented in pure Python so the image stays small and startup is instant.
- **LLM** (`app/llm.py`): calls OpenRouter's OpenAI-compatible API. It asks OpenRouter which models are currently free (`pricing = 0`), prefers gpt-oss / Llama / Gemma / Qwen, and falls through to the next model on rate limits or errors. Set `OPENROUTER_MODELS` to pin specific ones.
- **Grounding**: the prompt tells the model to answer only from numbered passages, cite them, and say so when the data doesn't cover the question. If every free model fails, the app still returns the best-matching passages instead of an error.
- **UI** (`static/index.html`): single-page chat with clickable sources.
- `data/seed/` holds a small starter dataset so the deployed bot works before you run the scraper. Scraped data is added on top.

## Run locally
```bash
cp .env.example .env            # add your OpenRouter key (free at openrouter.ai/keys)
docker build -t property-chatbot .
docker run --rm -p 7860:7860 --env-file .env property-chatbot
# open http://localhost:7860
```
Without Docker: `pip install -r requirements.txt && OPENROUTER_API_KEY=... uvicorn app.main:app --port 7860`

## Refresh the data (run on your own machine)
```bash
pip install -r requirements-scraper.txt
python -m scraper.scrape --delay 1.5          # writes data/scraped/darglobal.jsonl and wasalt.jsonl
```
Rebuild the image afterwards so the new files are baked in. Check each site's terms before scraping.

## Deploy (free) 
**Hugging Face Spaces (recommended):**
1. Create a new Space, SDK **Docker**, and push this repo to it (`git push` to the Space remote). The front matter above sets the port.
2. Space **Settings → Variables and secrets** → add secret `OPENROUTER_API_KEY`.
3. The public URL is `https://<user>-<space-name>.hf.space`.

**Render:** New → Blueprint → select this repo (uses `render.yaml`); set `OPENROUTER_API_KEY` when prompted. Free instances sleep when idle, so the first request can take about a minute.

## API
- `GET /health` → status and number of indexed chunks per site
- `POST /chat` with `{"message": "...", "history": [{"role": "user", "content": "..."}]}` → `{"answer", "sources", "model"}`

## Tests
`pip install pytest && python -m pytest tests`

## Limitations
- BM25 finds relevant passages but can't aggregate across listings (e.g. "average price in Riyadh"); a vector store plus structured filters would be the next step.
- Free OpenRouter models are rate-limited and change over time; the fallback logic handles this but answer quality varies by model.
- Listing data is a snapshot; prices and availability may be out of date.
