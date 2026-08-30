#!/usr/bin/env python3
"""Lightweight collector for Opportunity Intelligence OS.

V1 deliberately does NOT pretend to be a full AI analyst. It gathers fresh official
headlines, scores source/recency/category deterministically, and appends them to a
raw feed. Curated opportunity hypotheses remain separate in data/radar.json.

Why this design: a bad autonomous LLM can create convincing but false opportunities.
V1 keeps evidence collection automatic and opportunity generation auditable.
"""
from __future__ import annotations
import json, re, sys, hashlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "pipeline" / "config.json").read_text(encoding="utf-8"))
OUT = ROOT / "data" / "raw_feed.json"
UA = "Mozilla/5.0 (compatible; OpportunityIntelligenceOS/1.0; +https://github.com/)"


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def classify(text: str):
    t = text.lower()
    hits = []
    for sector, kws in CONFIG["keywords"].items():
        n = sum(1 for kw in kws if kw in t)
        if n:
            hits.append((sector, n))
    hits.sort(key=lambda x: x[1], reverse=True)
    return [h[0] for h in hits[:3]]


def fetch_source(src):
    try:
        r = requests.get(src["url"], timeout=20, headers={"User-Agent": UA})
        r.raise_for_status()
    except Exception as e:
        return [], f"{src['name']}: {type(e).__name__}: {e}"
    soup = BeautifulSoup(r.text, "html.parser")
    items = []
    seen = set()
    host = urlparse(src["url"]).netloc
    for a in soup.find_all("a", href=True):
        title = norm(a.get_text(" ", strip=True))
        if len(title) < 25 or len(title) > 220:
            continue
        href = urljoin(src["url"], a["href"])
        if urlparse(href).netloc != host:
            continue
        cats = classify(title)
        if not cats:
            continue
        key = hashlib.sha1((title + href).encode("utf-8")).hexdigest()[:16]
        if key in seen:
            continue
        seen.add(key)
        items.append({
            "id": key,
            "source_id": src["id"],
            "publisher": src["name"],
            "title": title,
            "url": href,
            "categories": cats,
            "authority": src["authority"],
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "status": "unverified-headline"
        })
    return items[:60], None


def main():
    old = {"updated_at": None, "items": [], "errors": []}
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            pass
    merged = {x["id"]: x for x in old.get("items", [])}
    errors = []
    for src in CONFIG["sources"]:
        items, err = fetch_source(src)
        if err:
            errors.append(err)
        for x in items:
            merged[x["id"]] = x
    rows = list(merged.values())
    rows.sort(key=lambda x: x.get("collected_at", ""), reverse=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "items": rows[:500],
        "errors": errors
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {len(payload['items'])} items; errors={len(errors)}")
    for e in errors:
        print(e, file=sys.stderr)


if __name__ == "__main__":
    main()
