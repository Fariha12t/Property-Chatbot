# DarGlobal and Wasalt assistant

A retrieval-augmented chatbot that answers questions about **DarGlobal** (luxury branded-residence developer) and **Wasalt** (Saudi property marketplace), using data collected from their public websites and a **free OpenRouter model**. Containerised with Docker and deployed to a public URL.

**Live demo: https://property-chatbot-jb3a.onrender.com**

> Hosted on Render's free tier, which sleeps when idle. The first request after a pause can take up to a minute.

```
scraper/scrape.py  ->  data/scraped/*.jsonl ─┐
data/seed/*.jsonl (starter dataset) ─────────┴->  BM25 index  ->  FastAPI /chat  ->  OpenRouter free model  ->  answer + sources
```

## How it works
- **Scraping** (`scraper/scrape.py`): reads each site's `robots.txt` and sitemap, falls back to link crawling, extracts page text (plus JSON-LD / Next.js embedded data for JS-heavy pages), waits between requests, and skips anything robots.txt disallows.
- **Retrieval** (`app/rag.py`): chunking plus BM25, implemented in pure Python so the image stays small and startup is instant.
- **LLM** (`app/llm.py`): calls OpenRouter's OpenAI-compatible API. It asks OpenRouter which models are currently free (`pricing = 0`), prefers gpt-oss / Llama / Gemma / Qwen, and falls through to the next model on rate limits or errors. Set `OPENROUTER_MODELS` to pin specific ones.
- **Grounding**: the prompt tells the model to answer only from numbered passages, cite them, and say so when the data doesn't cover the question. If every free model fails, the app returns the best-matching passages instead of an error.
- **UI** (`static/index.html`): single-page chat with clickable sources.

## Data
| Source | Contents |
|---|---|
| darglobal.co.uk | 57 scraped pages (projects, partners, FAQ, press, blog) plus a small starter set; about 433 indexed chunks |
| wasalt.sa | Platform overview plus 12 sample listings compiled from public Wasalt pages (13 chunks) |

`data/seed/` holds the starter dataset so the bot works before any scraping. Scraped data in `data/scraped/` is added on top.

## Run locally
```bash
cp .env.example .env            # add your OpenRouter key (free at openrouter.ai/keys)
docker build -t property-chatbot .
docker run --rm -p 7860:7860 --env-file .env property-chatbot
# open http://localhost:7860
```
Without Docker: `pip install -r requirements.txt && OPENROUTER_API_KEY=... uvicorn app.main:app --port 7860`

## Refresh the data
```bash
pip install -r requirements-scraper.txt
python -m scraper.scrape --delay 1.5 --max-pages 60   # writes data/scraped/<site>.jsonl
```
Rebuild the image afterwards so the new files are included. Check each site's terms before scraping.

## Deploy (Render)
1. Push this repo to GitHub.
2. In Render: **New → Blueprint**, select the repo (it uses `render.yaml`).
3. Set the `OPENROUTER_API_KEY` environment variable when prompted. Never commit it; `.env` is git-ignored.

## API
- `GET /health` → status and number of indexed chunks per site
- `POST /chat` with `{"message": "...", "history": [{"role": "user", "content": "..."}]}` → `{"answer", "sources", "model"}`

## Tests
`pip install pytest && python -m pytest tests`

## Limitations
- **Wasalt coverage is limited:** the live scrape of wasalt.sa did not add pages, so Wasalt answers rely on the sample listings, which are a point-in-time snapshot.
- BM25 finds relevant passages but can't aggregate across listings (e.g. "average price in Riyadh"); a vector store plus structured filters would be the next step.
- Free OpenRouter models are rate-limited and change over time; the fallback logic handles this but answer quality varies by model.
- Prices and availability may have changed since the data was collected.
