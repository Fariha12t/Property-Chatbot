"""Small BM25 retriever over DarGlobal and Wasalt pages (no heavy ML dependencies)."""
import json
import math
import re
from collections import Counter
from pathlib import Path

STOP = set(
    "a an the and or of to in on at for from with by is are was were be been it this that these those "
    "what which who whom how do does did can could should would will you your i me my we our us about "
    "tell show any some there their them as if than then also please give list".split()
)


def tok(text: str) -> list[str]:
    text = re.sub(r"(?<=\d),(?=\d{3})", "", text.lower())
    out = []
    for w in re.findall(r"\w+", text):
        if w in STOP:
            continue
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return out


def chunk_text(text: str, size: int = 900) -> list[str]:
    chunks, cur = [], ""
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if cur and len(cur) + len(line) + 1 > size:
            chunks.append(cur)
            cur = cur[-150:].split(" ", 1)[-1] + " " + line  # small overlap between chunks
        else:
            cur = f"{cur}\n{line}" if cur else line
    if cur:
        chunks.append(cur)
    return chunks


def load_docs(data_dir: Path) -> list[dict]:
    """Load data/seed/*.jsonl and data/scraped/*.jsonl, de-duplicated by (url, title)."""
    docs: dict[tuple, dict] = {}
    for sub in ("seed", "scraped"):
        for f in sorted((data_dir / sub).glob("*.jsonl")):
            for line in f.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                    docs[(d["url"], d["title"])] = d
                except (ValueError, KeyError):
                    print(f"skipping bad line in {f.name}", flush=True)
    return list(docs.values())


class Index:
    def __init__(self, docs: list[dict]):
        self.chunks = []
        for d in docs:
            for c in chunk_text(d["text"]):
                self.chunks.append({"site": d["site"], "url": d["url"], "title": d["title"], "text": c})
        self.tf = [Counter(tok(c["title"] + " " + c["text"])) for c in self.chunks]
        self.dl = [sum(t.values()) for t in self.tf]
        self.avg = (sum(self.dl) / len(self.dl)) if self.dl else 1.0
        self.df = Counter(w for t in self.tf for w in t)

    def stats(self) -> dict:
        return dict(Counter(c["site"] for c in self.chunks))

    def search(self, query: str, k: int = 5) -> list[dict]:
        q = tok(query)
        n = len(self.chunks)
        if not q or not n:
            return []
        qlow = query.lower()
        scored = []
        for i, tf in enumerate(self.tf):
            s = 0.0
            for w in q:
                f = tf.get(w, 0)
                if not f:
                    continue
                idf = math.log(1 + (n - self.df[w] + 0.5) / (self.df[w] + 0.5))
                s += idf * f * 2.5 / (f + 1.5 * (0.25 + 0.75 * self.dl[i] / self.avg))
            if s and self.chunks[i]["site"] in qlow:
                s *= 1.3
            if s:
                scored.append((s, i))
        scored.sort(reverse=True)
        out, per_url = [], Counter()
        for s, i in scored:
            c = self.chunks[i]
            if per_url[c["url"]] >= 2:
                continue
            per_url[c["url"]] += 1
            out.append({**c, "score": round(s, 3)})
            if len(out) == k:
                break
        return out
