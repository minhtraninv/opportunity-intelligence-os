#!/usr/bin/env python3
"""Entity discovery from public economic RSS feeds.

Media headlines are discovery evidence, not primary proof. This module exists to
reduce blind spots: it asks which registered entities repeatedly appear around real
economic actions. Entity Convergence decides whether those sightings deserve deeper
investigation and keeps media-only convergence below primary-evidence status.
"""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REGISTRY_PATH = DATA / "entity_registry.json"
HISTORY_PATH = DATA / "entity_media_history.json"
OUTPUT = DATA / "entity_media_intelligence.json"

WINDOW_DAYS = 120
RECENT_DAYS = 30
MAX_HISTORY = 2000
UA = "Mozilla/5.0 (compatible; OpportunityIntelligenceOS/2.6; +https://github.com/)"

SOURCES = [
    {"id": "vnexpress-business", "name": "VnExpress Kinh doanh", "url": "https://vnexpress.net/rss/kinh-doanh.rss"},
    {"id": "tuoitre-business", "name": "Tuổi Trẻ Kinh doanh", "url": "https://tuoitre.vn/kinh-doanh.rss"},
    {"id": "thanhnien-economy", "name": "Thanh Niên Kinh tế", "url": "https://thanhnien.vn/rss/kinh-te.rss"},
    {"id": "vietnamplus-economy", "name": "VietnamPlus Kinh tế", "url": "https://www.vietnamplus.vn/rss/kinhte-311.rss"},
]

FAMILY_RULES = (
    ("labor", ("tuyển dụng", "tuyển nhân sự", "tuyển lao động", "việc làm", "nhân sự", "lao động")),
    ("project_execution", (
        "khởi công", "khánh thành", "đưa vào vận hành", "vận hành nhà máy", "vận hành dự án",
        "khai trương", "triển khai", "xây dựng", "mở rộng nhà máy", "nhà máy mới", "dự án",
        "công trình", "tăng công suất", "khu công nghiệp", "trung tâm dữ liệu", "đường sắt", "sân bay", "cảng",
    )),
    ("capital", (
        "huy động vốn", "phát hành", "trái phiếu", "vay vốn", "khoản vay", "tín dụng", "góp vốn",
        "mua cổ phần", "tăng vốn", "rót vốn", "đầu tư thêm", "vốn đầu tư",
    )),
    ("operating", (
        "doanh thu", "lợi nhuận", "sản lượng", "doanh số", "bàn giao", "thị phần", "xuất khẩu",
        "tăng trưởng", "tiêu thụ", "đơn hàng", "khách hàng", "đặt mua", "hợp đồng mua",
    )),
    ("strategy", (
        "chiến lược", "kế hoạch", "đề xuất", "hợp tác", "liên doanh", "mua lại", "thâu tóm",
        "thành lập", "mở mảng", "tham gia", "định hướng", "mục tiêu", "thoái vốn", "bán mảng",
        "bán cổ phần", "chuyển nhượng", "tái cấu trúc",
    )),
    ("policy", ("nghị quyết", "nghị định", "chính sách", "cơ chế", "quy hoạch", "phê duyệt", "chấp thuận")),
)

STOPWORDS = {
    "của", "và", "cho", "với", "tại", "trong", "trên", "được", "sẽ", "đang", "vừa", "mới",
    "một", "các", "những", "từ", "đến", "về", "theo", "sau", "trước", "khi", "này", "đó",
    "tỷ", "triệu", "đồng", "usd", "việt", "nam", "công", "ty", "tập", "đoàn",
}


def build_session() -> requests.Session:
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        status=2,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": UA, "Accept-Language": "vi-VN,vi;q=0.9"})
    return session


SESSION = build_session()


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def write(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def norm(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None


def alias_match(text: str, aliases: list[str]) -> bool:
    for alias in aliases:
        if re.search(rf"(?<!\w){re.escape(str(alias))}(?!\w)", text, flags=re.IGNORECASE | re.UNICODE):
            return True
    return False


def classify(text: str) -> str | None:
    lowered = norm(text).casefold()

    # Observable customer demand should not be mistaken for project execution just
    # because the product will later be "operated" by a buyer.
    if re.search(r"\bmua\s+[\d\.,]+\s+(?:ô\s*tô|oto|xe|sản phẩm)", lowered, flags=re.UNICODE):
        return "operating"

    for family, phrases in FAMILY_RULES:
        if any(phrase.casefold() in lowered for phrase in phrases):
            return family
    return None


def signature(entity_id: str, family: str, title: str) -> str:
    words = re.findall(r"[\wÀ-ỹ]+", title.casefold(), flags=re.UNICODE)
    tokens = sorted({x for x in words if len(x) >= 4 and x not in STOPWORDS})[:12]
    raw = f"{entity_id}|{family}|{'|'.join(tokens)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def item_id(source_id: str, link: str, title: str) -> str:
    raw = f"{source_id}|{link}|{title.casefold()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def parse_rss(source: dict, registry: list[dict], captured_at: datetime) -> tuple[list[dict], str | None]:
    try:
        response = SESSION.get(source["url"], timeout=(10, 30))
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except Exception as exc:
        return [], f"{source['name']}: {type(exc).__name__}: {exc}"

    output = []
    for item in root.findall(".//item")[:80]:
        title = norm(item.findtext("title") or "")
        link = norm(item.findtext("link") or "")
        description = norm(item.findtext("description") or "")
        published = parse_date(item.findtext("pubDate")) or captured_at
        text = f"{title} {description}"
        if len(title) < 8:
            continue

        for entity in registry:
            aliases = entity.get("aliases") or []
            if not aliases or not alias_match(text, aliases):
                continue
            family = classify(text)
            if not family:
                continue
            output.append({
                "id": item_id(source["id"], link, title),
                "event_signature": signature(entity.get("id"), family, title),
                "entity_id": entity.get("id"),
                "entity_label": entity.get("label"),
                "entity_type": entity.get("entity_type"),
                "family": family,
                "title": title,
                "summary": description[:360],
                "publisher": source["name"],
                "source_url": link or source["url"],
                "published_at": published.isoformat(),
                "first_seen_at": captured_at.isoformat(),
                "last_seen_at": captured_at.isoformat(),
                "evidence_grade": "media_discovery",
            })
    return output, None


def merge_history(old: dict, fresh: list[dict], captured_at: datetime) -> dict:
    items = {str(x.get("id")): dict(x) for x in old.get("events", []) if isinstance(x, dict) and x.get("id")}
    refresh_fields = (
        "event_signature", "entity_id", "entity_label", "entity_type", "family", "title",
        "summary", "publisher", "source_url", "published_at", "evidence_grade",
    )
    for event in fresh:
        key = str(event.get("id"))
        if key in items:
            existing = items[key]
            for field in refresh_fields:
                if event.get(field) is not None:
                    existing[field] = event.get(field)
            existing["last_seen_at"] = captured_at.isoformat()
        else:
            items[key] = event

    cutoff = captured_at - timedelta(days=WINDOW_DAYS)
    rows = []
    for event in items.values():
        dt = parse_date(event.get("published_at") or event.get("first_seen_at"))
        if dt and dt < cutoff:
            continue
        rows.append(event)
    rows.sort(key=lambda x: x.get("published_at") or "", reverse=True)
    return {"version": 1, "updated_at": captured_at.isoformat(), "events": rows[:MAX_HISTORY]}


def main() -> None:
    now = datetime.now(timezone.utc)
    registry = load(REGISTRY_PATH, {}).get("entities", [])
    history = load(HISTORY_PATH, {"events": []})

    fresh = []
    health = []
    for source in SOURCES:
        rows, error = parse_rss(source, registry, now)
        fresh.extend(rows)
        health.append({
            "source_id": source["id"],
            "publisher": source["name"],
            "status": "error" if error else "ok",
            "items_this_run": len(rows),
            "error": error,
        })

    merged = merge_history(history, fresh, now)
    write(HISTORY_PATH, merged)

    cutoff = now - timedelta(days=RECENT_DAYS)
    recent = []
    for event in merged.get("events", []):
        dt = parse_date(event.get("published_at") or event.get("first_seen_at"))
        if not dt or dt >= cutoff:
            recent.append(event)

    counts = {}
    for event in recent:
        key = event.get("entity_id")
        counts[key] = counts.get(key, 0) + 1

    payload = {
        "meta": {
            "version": "2.6.2",
            "generated_at": now.isoformat(),
            "mode": "economic_media_entity_discovery",
            "principle": "media_creates_investigation_triggers_not_primary_truth"
        },
        "coverage": {
            "sources": len(SOURCES),
            "healthy_sources": sum(1 for x in health if x.get("status") == "ok"),
            "recent_events": len(recent),
            "entities_seen_recently": len(counts),
            "history_events": len(merged.get("events", [])),
        },
        "source_health": health,
        "entity_counts": [
            {"entity_id": key, "recent_events": value}
            for key, value in sorted(counts.items(), key=lambda x: x[1], reverse=True)
        ],
        "events": recent[:400],
        "warnings": [
            "Media headline chỉ là discovery trigger; không phải bằng chứng cuối cùng.",
            "Nhiều báo có thể đưa cùng một sự kiện; Entity Convergence phải ưu tiên evidence family chứ không đếm headline thô.",
            "Không suy ra cơ hội đầu tư/kinh doanh chỉ vì một entity xuất hiện nhiều trên báo."
        ]
    }
    write(OUTPUT, payload)
    print(
        f"entity-media healthy={payload['coverage']['healthy_sources']}/{len(SOURCES)} "
        f"recent={len(recent)} entities={len(counts)}"
    )


if __name__ == "__main__":
    main()
