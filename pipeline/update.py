#!/usr/bin/env python3
"""Opportunity Intelligence OS collector + deterministic Change Detector.

V1.1 responsibilities:
1) collect relevant public headlines from configured sources;
2) preserve first-seen history instead of making old headlines look new every run;
3) build a conservative change detector from observed event history;
4) reclassify stored machine-collected data when the taxonomy improves.

The detector deliberately refuses to claim momentum until it has enough history.
It does not generate business opportunities automatically; curated hypotheses remain
separate in data/radar.json.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "pipeline" / "config.json"
RAW_PATH = ROOT / "data" / "raw_feed.json"
HISTORY_PATH = ROOT / "data" / "history.json"
INTELLIGENCE_PATH = ROOT / "data" / "intelligence.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
UA = "Mozilla/5.0 (compatible; OpportunityIntelligenceOS/1.1; +https://github.com/)"

HISTORY_EVENT_LIMIT = 5000
SNAPSHOT_LIMIT = 720
RAW_FEED_LIMIT = 1000
MIN_HISTORY_DAYS = 14
RECENT_DAYS = 7
BASELINE_DAYS = 21


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def keyword_matches(text: str, keyword: str) -> bool:
    """Match whole words/phrases, not arbitrary substrings.

    This prevents false positives such as 'ai' inside 'triển khai'. Python's Unicode
    \w handling is used so Vietnamese letters are treated as word characters.
    """
    pattern = rf"(?<!\w){re.escape(keyword.lower())}(?!\w)"
    return re.search(pattern, text.lower(), flags=re.UNICODE) is not None


def classify(text: str) -> list[str]:
    normalized = norm(text).lower()
    hits = []
    for sector, keywords in CONFIG["keywords"].items():
        score = sum(1 for keyword in keywords if keyword_matches(normalized, keyword))
        if score:
            hits.append((sector, score))
    hits.sort(key=lambda x: (-x[1], x[0]))
    return [sector for sector, _ in hits[:3]]


def clean_href(raw_href: str) -> str:
    return re.sub(r"[\r\n\t]+", "", raw_href or "").strip()


def fetch_source(src: dict) -> tuple[list[dict], str | None]:
    try:
        response = requests.get(src["url"], timeout=20, headers={"User-Agent": UA})
        response.raise_for_status()
    except Exception as exc:
        return [], f"{src['name']}: {type(exc).__name__}: {exc}"

    soup = BeautifulSoup(response.text, "html.parser")
    host = urlparse(src["url"]).netloc
    items = []
    seen = set()

    for anchor in soup.find_all("a", href=True):
        title = norm(anchor.get_text(" ", strip=True))
        if len(title) < 25 or len(title) > 220:
            continue

        raw_href = clean_href(anchor["href"])
        if not raw_href:
            continue
        href = urljoin(src["url"], raw_href)
        if urlparse(href).netloc != host:
            continue

        categories = classify(title)
        if not categories:
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
            "categories": categories,
            "authority": src["authority"],
            "status": "unverified-headline",
        })

    return items[:60], None


def clean_stored_item(item: dict) -> dict | None:
    if not item.get("id") or not item.get("title"):
        return None
    cleaned = dict(item)
    if cleaned.get("status") == "verified-seed":
        return cleaned
    categories = classify(cleaned.get("title", ""))
    if not categories:
        return None
    cleaned["categories"] = categories
    cleaned["url"] = clean_href(cleaned.get("url", ""))
    return cleaned


def merge_feed(old_items: list[dict], fetched_items: list[dict], captured_at: datetime) -> tuple[list[dict], list[dict]]:
    merged = {}
    for old_item in old_items:
        cleaned = clean_stored_item(old_item)
        if cleaned:
            merged[cleaned["id"]] = cleaned

    new_items = []
    captured_iso = iso(captured_at)

    for item in fetched_items:
        item_id = item["id"]
        previous = merged.get(item_id)

        if previous:
            first_seen = previous.get("first_seen_at") or previous.get("collected_at") or captured_iso
            status = previous.get("status", item.get("status", "unverified-headline"))
            merged[item_id] = {
                **previous,
                **item,
                "status": status,
                "collected_at": previous.get("collected_at") or first_seen,
                "first_seen_at": first_seen,
                "last_seen_at": captured_iso,
            }
        else:
            fresh = {
                **item,
                "collected_at": captured_iso,
                "first_seen_at": captured_iso,
                "last_seen_at": captured_iso,
            }
            merged[item_id] = fresh
            new_items.append(fresh)

    rows = list(merged.values())
    rows.sort(key=lambda x: x.get("first_seen_at") or x.get("collected_at") or "", reverse=True)
    return rows[:RAW_FEED_LIMIT], new_items


def event_from_item(item: dict) -> dict:
    return {
        "id": item["id"],
        "source_id": item.get("source_id"),
        "publisher": item.get("publisher"),
        "title": item.get("title"),
        "url": item.get("url"),
        "categories": item.get("categories", []),
        "authority": item.get("authority"),
        "status": item.get("status", "unverified-headline"),
        "first_seen_at": item.get("first_seen_at") or item.get("collected_at"),
    }


def clean_history_event(event: dict) -> dict | None:
    if not event.get("id") or not event.get("title"):
        return None
    cleaned = dict(event)
    if cleaned.get("status") == "verified-seed":
        return cleaned
    categories = classify(cleaned.get("title", ""))
    if not categories:
        return None
    cleaned["categories"] = categories
    cleaned["url"] = clean_href(cleaned.get("url", ""))
    return cleaned


def update_history(history: dict, feed_items: list[dict], new_items: list[dict], captured_at: datetime, errors: list[str]) -> dict:
    events_by_id = {}
    for event in history.get("events", []):
        cleaned = clean_history_event(event)
        if cleaned:
            events_by_id[cleaned["id"]] = cleaned

    # Bootstrap or repair history from the current cleaned feed.
    for item in feed_items:
        events_by_id[item["id"]] = event_from_item(item)

    events = list(events_by_id.values())
    events.sort(key=lambda x: x.get("first_seen_at") or "", reverse=True)
    events = events[:HISTORY_EVENT_LIMIT]

    category_counts = defaultdict(int)
    source_counts = defaultdict(int)
    for item in new_items:
        source_counts[item.get("source_id") or "unknown"] += 1
        for category in item.get("categories", []):
            category_counts[category] += 1

    snapshots = list(history.get("snapshots", []))
    snapshots.append({
        "captured_at": iso(captured_at),
        "new_items": len(new_items),
        "new_by_category": dict(sorted(category_counts.items())),
        "new_by_source": dict(sorted(source_counts.items())),
        "total_events": len(events),
        "source_errors": len(errors),
    })
    snapshots = snapshots[-SNAPSHOT_LIMIT:]

    return {
        "version": 1,
        "updated_at": iso(captured_at),
        "events": events,
        "snapshots": snapshots,
    }


def history_span_days(events: list[dict], captured_at: datetime) -> int:
    dates = [
        parse_dt(event.get("first_seen_at"))
        for event in events
        if event.get("status") != "verified-seed"
    ]
    dates = [dt for dt in dates if dt is not None]
    if not dates:
        return 0
    oldest = min(dates)
    return max(1, (captured_at - oldest).days + 1)


def category_change_stats(events: list[dict], captured_at: datetime, history_days: int) -> list[dict]:
    eligible = [
        event for event in events
        if event.get("status") != "verified-seed" and parse_dt(event.get("first_seen_at"))
    ]

    results = []
    recent_start = captured_at - timedelta(days=RECENT_DAYS)
    baseline_start = recent_start - timedelta(days=BASELINE_DAYS)

    for category in CONFIG["keywords"].keys():
        recent_events = []
        baseline_events = []

        for event in eligible:
            if category not in event.get("categories", []):
                continue
            seen_at = parse_dt(event.get("first_seen_at"))
            if seen_at is None:
                continue
            if recent_start <= seen_at <= captured_at:
                recent_events.append(event)
            elif baseline_start <= seen_at < recent_start:
                baseline_events.append(event)

        recent_count = len(recent_events)
        baseline_count = len(baseline_events)
        expected_7d = baseline_count / (BASELINE_DAYS / RECENT_DAYS)
        source_diversity = len({e.get("source_id") for e in recent_events if e.get("source_id")})

        if history_days < MIN_HISTORY_DAYS:
            trend = "warming_up"
            delta_pct = None
        elif expected_7d < 1 and recent_count >= 5:
            trend = "emerging"
            delta_pct = None
        elif expected_7d >= 2:
            ratio = recent_count / expected_7d if expected_7d else 0
            absolute_gap = recent_count - expected_7d
            if ratio >= 1.5 and absolute_gap >= 2:
                trend = "accelerating"
            elif ratio <= 0.6 and absolute_gap <= -2:
                trend = "cooling"
            else:
                trend = "stable"
            delta_pct = round((ratio - 1) * 100)
        else:
            trend = "insufficient_sample"
            delta_pct = None

        history_score = min(40, (history_days / 28) * 40)
        sample_score = min(40, ((recent_count + baseline_count) / 20) * 40)
        source_score = min(20, (source_diversity / 3) * 20)
        confidence = round(history_score + sample_score + source_score)

        if history_days < MIN_HISTORY_DAYS:
            explanation = f"Đang học baseline: mới có {history_days}/{MIN_HISTORY_DAYS} ngày lịch sử. Chưa kết luận xu hướng."
        elif trend == "accelerating":
            explanation = f"7 ngày gần nhất có {recent_count} tín hiệu; baseline quy đổi 7 ngày là {expected_7d:.1f}."
        elif trend == "cooling":
            explanation = f"Tần suất tín hiệu giảm: {recent_count} trong 7 ngày so với baseline {expected_7d:.1f}."
        elif trend == "emerging":
            explanation = f"Xuất hiện {recent_count} tín hiệu trong 7 ngày trong khi baseline trước đó gần như trống."
        elif trend == "stable":
            explanation = "Tần suất hiện tại chưa lệch đủ xa khỏi baseline để coi là bất thường."
        else:
            explanation = "Mẫu còn quá nhỏ để phân biệt thay đổi thật với nhiễu."

        results.append({
            "category": category,
            "recent_7d": recent_count,
            "baseline_21d": baseline_count,
            "baseline_expected_7d": round(expected_7d, 1),
            "delta_pct": delta_pct,
            "trend": trend,
            "confidence": confidence,
            "source_diversity_7d": source_diversity,
            "explanation": explanation,
        })

    priority = {
        "accelerating": 5,
        "emerging": 4,
        "stable": 3,
        "cooling": 2,
        "insufficient_sample": 1,
        "warming_up": 0,
    }
    results.sort(key=lambda x: (priority.get(x["trend"], 0), x["confidence"], x["recent_7d"]), reverse=True)
    return results


def build_intelligence(history: dict, captured_at: datetime, errors: list[str]) -> dict:
    events = history.get("events", [])
    history_days = history_span_days(events, captured_at)
    changes = category_change_stats(events, captured_at, history_days)

    recent_24h_cutoff = captured_at - timedelta(hours=24)
    top_new_events = []
    for event in events:
        seen_at = parse_dt(event.get("first_seen_at"))
        if seen_at and seen_at >= recent_24h_cutoff and event.get("status") != "verified-seed":
            top_new_events.append(event)
    top_new_events = top_new_events[:20]

    status = "active" if history_days >= MIN_HISTORY_DAYS else "warming_up"
    warnings = []
    if status == "warming_up":
        warnings.append(
            f"Change Detector đang học baseline ({history_days}/{MIN_HISTORY_DAYS} ngày). "
            "Không coi các chênh lệch hiện tại là trend."
        )
    if errors:
        warnings.append(f"Có {len(errors)} nguồn lỗi ở lần thu thập gần nhất; độ phủ dữ liệu bị giảm.")

    unique_sources = {event.get("source_id") for event in events if event.get("source_id")}
    non_seed_events = [event for event in events if event.get("status") != "verified-seed"]

    return {
        "meta": {
            "generated_at": iso(captured_at),
            "status": status,
            "history_days": history_days,
            "required_history_days": MIN_HISTORY_DAYS,
            "recent_window_days": RECENT_DAYS,
            "baseline_window_days": BASELINE_DAYS,
            "method": "deterministic_frequency_change_v1",
        },
        "category_changes": changes,
        "top_new_events": top_new_events,
        "coverage": {
            "historical_events": len(events),
            "machine_collected_events": len(non_seed_events),
            "unique_sources": len(unique_sources),
            "source_errors_last_run": len(errors),
        },
        "warnings": warnings,
    }


def main() -> None:
    captured_at = now_utc()
    old_feed = load_json(RAW_PATH, {"updated_at": None, "items": [], "errors": []})

    fetched = []
    errors = []
    for source in CONFIG["sources"]:
        items, error = fetch_source(source)
        fetched.extend(items)
        if error:
            errors.append(error)

    feed_rows, new_items = merge_feed(old_feed.get("items", []), fetched, captured_at)
    raw_payload = {
        "updated_at": iso(captured_at),
        "items": feed_rows,
        "errors": errors,
    }
    write_json(RAW_PATH, raw_payload)

    old_history = load_json(HISTORY_PATH, {"version": 1, "events": [], "snapshots": []})
    history = update_history(old_history, feed_rows, new_items, captured_at, errors)
    write_json(HISTORY_PATH, history)

    intelligence = build_intelligence(history, captured_at, errors)
    write_json(INTELLIGENCE_PATH, intelligence)

    print(
        f"saved feed={len(feed_rows)} new={len(new_items)} "
        f"history={len(history['events'])} status={intelligence['meta']['status']} "
        f"errors={len(errors)}"
    )
    for error in errors:
        print(error, file=sys.stderr)


if __name__ == "__main__":
    main()
