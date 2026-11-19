#!/usr/bin/env python3
"""Scrape public pages from DarGlobal and Wasalt into data/scraped/<site>.jsonl.

Polite by design: honours robots.txt, identifies itself, waits between requests, and caps page counts.
Run from the project root:

    pip install -r requirements-scraper.txt
    python -m scraper.scrape                      # both sites
    python -m scraper.scrape --sites wasalt --max-pages 80 --delay 1.5
"""
import argparse
import gzip
import json
import random
import re
import time
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (compatible; PropertyChatbotAssignmentBot/1.0; educational use)"
OUT = Path(__file__).resolve().parent.parent / "data" / "scraped"
SKIP_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".pdf", ".zip", ".mp4", ".css", ".js", ".ico", ".xml")

SITES = {
    "darglobal": {"base": "https://darglobal.co.uk", "seeds": ["/"], "max_pages": 120, "max_listings": 0, "prefix": ""},
    # Wasalt has a huge number of listing pages; take all non-listing pages plus a sample of listings.
    "wasalt": {"base": "https://wasalt.sa", "seeds": ["/en"], "max_pages": 140, "max_listings": 100, "prefix": "/en"},
}


class Fetcher:
    def __init__(self, base: str, delay: float):
        self.base, self.delay, self.last = base, delay, 0.0
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept-Language": "en"})
        self.robots = RobotFileParser()
        self.sitemaps: list[str] = []
        try:
            r = self.s.get(base + "/robots.txt", timeout=15)
            self.robots.parse(r.text.splitlines() if r.ok else [])
            self.sitemaps = re.findall(r"(?im)^sitemap:\s*(\S+)", r.text) if r.ok else []
        except requests.RequestException:
            self.robots.parse([])

    def allowed(self, url: str) -> bool:
        return self.robots.can_fetch(UA, url)

    def get(self, url: str) -> str | None:
        if not self.allowed(url):
            print(f"  robots.txt disallows {url}")
            return None
        wait = self.delay - (time.time() - self.last)
        if wait > 0:
            time.sleep(wait)
        for attempt in range(3):
            try:
                self.last = time.time()
                r = self.s.get(url, timeout=25)
                if r.status_code == 200:
                    if r.content[:2] == b"\x1f\x8b":
                        return gzip.decompress(r.content).decode("utf-8", "ignore")
                    return r.text
                if r.status_code in (429, 503):
                    time.sleep(5 * (attempt + 1))
                    continue
                return None
            except requests.RequestException:
                time.sleep(2)
        return None


def sitemap_urls(f: Fetcher, limit_maps: int = 15, limit_urls: int = 20000) -> list[str]:
    todo = f.sitemaps or [f.base + "/sitemap.xml", f.base + "/sitemap_index.xml"]
    seen, urls, maps = set(), [], 0
    while todo and maps < limit_maps and len(urls) < limit_urls:
        sm = todo.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        xml = f.get(sm)
        if not xml:
            continue
        maps += 1
        for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", xml):
            loc = loc.replace("&amp;", "&")
            if loc.endswith((".xml", ".xml.gz")):
                todo.append(loc)
            else:
                urls.append(loc)
    return urls


def flatten_strings(obj, out: list[str], depth: int = 0) -> None:
    """Collect human-readable strings from embedded JSON (JSON-LD / Next.js data)."""
    if depth > 12:
        return
    if isinstance(obj, str):
        if 20 <= len(obj) <= 800 and not obj.startswith(("http", "/", "data:")):
            out.append(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (str, int, float)) and k.lower() in ("price", "bedrooms", "bathrooms", "area", "city", "district", "name"):
                out.append(f"{k}: {v}")
            else:
                flatten_strings(v, out, depth + 1)
    elif isinstance(obj, list):
        for v in obj[:200]:
            flatten_strings(v, out, depth + 1)


def extract(html: str, url: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.get_text(strip=True) if soup.title else "") or url
    desc = ""
    m = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    if m and m.get("content"):
        desc = m["content"].strip()

    embedded: list[str] = []
    for tag in soup.find_all("script"):
        if tag.get("type") == "application/ld+json" or tag.get("id") == "__NEXT_DATA__":
            try:
                flatten_strings(json.loads(tag.string or ""), embedded)
            except (ValueError, TypeError):
                pass

    for t in soup(["script", "style", "noscript", "svg", "nav", "footer", "iframe", "form"]):
        t.decompose()
    root = soup.find("main") or soup.body or soup
    lines, prev = [], ""
    for raw in root.get_text("\n").split("\n"):
        line = re.sub(r"\s+", " ", raw).strip()
        if len(line) > 1 and line != prev:
            lines.append(line)
        prev = line
    text = "\n".join(([desc] if desc else []) + lines)
    if len(text) < 300 and embedded:  # JS-heavy page: fall back to embedded data
        text += "\n" + "\n".join(dict.fromkeys(embedded))
    if len(text) < 120:
        return None
    return {"url": url, "title": title[:200], "text": text[:12000]}


def clean(url: str) -> str:
    return urldefrag(url)[0].rstrip("/") or url


def choose_urls(f: Fetcher, cfg: dict, site: str) -> list[str]:
    host = urlparse(cfg["base"]).netloc
    urls = [clean(u) for u in sitemap_urls(f)]
    urls = [u for u in dict.fromkeys(urls)
            if urlparse(u).netloc == host and not u.lower().endswith(SKIP_EXT)
            and urlparse(u).path.startswith(cfg["prefix"])]
    print(f"[{site}] sitemap gave {len(urls)} candidate URLs")
    pages = sorted((u for u in urls if "/property/" not in u), key=len)
    listings = [u for u in urls if "/property/" in u]
    random.Random(7).shuffle(listings)
    chosen = pages[: cfg["max_pages"]] + listings[: cfg["max_listings"]]
    return chosen[: cfg["max_pages"] + cfg["max_listings"]]


def crawl_links(f: Fetcher, cfg: dict, limit: int) -> list[str]:
    """Fallback when there is no usable sitemap: breadth-first over internal links."""
    host = urlparse(cfg["base"]).netloc
    queue = [clean(urljoin(cfg["base"], s)) for s in cfg["seeds"]]
    seen, order = set(queue), []
    while queue and len(order) < limit:
        url = queue.pop(0)
        order.append(url)
        html = f.get(url)
        if not html:
            continue
        for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
            link = clean(urljoin(url, a["href"]))
            p = urlparse(link)
            if (p.netloc == host and link not in seen and p.path.startswith(cfg["prefix"])
                    and not link.lower().endswith(SKIP_EXT)):
                seen.add(link)
                queue.append(link)
    return order


def scrape_site(site: str, delay: float, max_pages: int | None) -> int:
    cfg = dict(SITES[site])
    if max_pages:
        cfg["max_pages"] = max_pages
        cfg["max_listings"] = min(cfg["max_listings"], max_pages // 2)
    f = Fetcher(cfg["base"], delay)
    urls = choose_urls(f, cfg, site)
    if len(urls) < 5:
        print(f"[{site}] no usable sitemap, crawling links instead")
        urls = crawl_links(f, cfg, cfg["max_pages"])
    OUT.mkdir(parents=True, exist_ok=True)
    path, n = OUT / f"{site}.jsonl", 0
    with path.open("w", encoding="utf-8") as fh:
        for i, url in enumerate(urls, 1):
            html = f.get(url)
            doc = extract(html, url) if html else None
            print(f"[{site}] {i}/{len(urls)} {'ok  ' if doc else 'skip'} {url}")
            if doc:
                fh.write(json.dumps({"site": site, **doc}, ensure_ascii=False) + "\n")
                n += 1
    print(f"[{site}] saved {n} pages to {path}")
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sites", nargs="+", choices=list(SITES), default=list(SITES))
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    ap.add_argument("--max-pages", type=int, default=None)
    args = ap.parse_args()
    for s in args.sites:
        scrape_site(s, args.delay, args.max_pages)


if __name__ == "__main__":
    main()
