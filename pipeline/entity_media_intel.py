#!/usr/bin/env python3
"""Open-world entity discovery from public economic RSS feeds.

Media headlines are discovery evidence, not primary proof. Known aliases are
normalized through entity_registry.json, while previously unknown organizations can
enter as conservative auto-discovered candidates. Registry membership contributes no
importance; auto-discovery contributes no importance either. Entity Convergence
later decides whether independent evidence deserves investigation.
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
UA = "Mozilla/5.0 (compatible; OpportunityIntelligenceOS/2.7; +https://github.com/)"

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

GENERIC_TITLE_STARTS = {
    "doanh nghiệp", "công ty", "tập đoàn", "ngân hàng", "nhà đầu tư", "chính phủ", "bộ",
    "quốc hội", "thị trường", "giá", "cổ phiếu", "chứng khoán", "vàng", "usd", "tỷ giá",
    "việt nam", "hà nội", "tp hcm", "tp.hcm", "thành phố", "mỹ", "trung quốc", "nhật bản",
    "hàn quốc", "eu", "asean", "người", "khách", "chuyên gia", "đề xuất", "dự án",
}

BRAND_SUFFIXES = {
    "group", "holdings", "holding", "bank", "airlines", "airways", "auto", "energy", "power",
    "telecom", "retail", "land", "homes", "motor", "motors", "steel", "tech", "technology",
    "vietnam", "vina", "global", "foods", "food", "pharma", "logistics",
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


def item_id(source_id: str, entity_id: str, link: str, title: str) -> str:
    raw = f"{source_id}|{entity_id}|{link}|{title.casefold()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def auto_entity_id(label: str) -> str:
    normalized = re.sub(r"\W+", "-", label.casefold(), flags=re.UNICODE).strip("-")
    digest = hashlib.sha1(label.casefold().encode("utf-8")).hexdigest()[:8]
    return f"auto-{normalized[:36]}-{digest}"


def starts_like_proper_name(token: str) -> bool:
    clean = token.strip("()[]{}'\"“”‘’,.:;!?+-/")
    if len(clean) < 2:
        return False
    first = clean[0]
    return first.isupper() or clean.isupper() or any(ch.isupper() for ch in clean[1:])


def extract_title_entity(title: str, description: str) -> str | None:
    """Conservatively infer a previously unknown organization from headline start.

    We only accept a leading proper-name phrase that also occurs in the RSS summary.
    This intentionally misses many entities; recall can be expanded later without
    sacrificing precision or turning ordinary sentence starts into fake companies.
    """
    clean_title = norm(title)
    clean_desc = norm(description)
    if not clean_title or not clean_desc:
        return None

    folded = clean_title.casefold()
    if any(folded == x or folded.startswith(x + " ") for x in GENERIC_TITLE_STARTS):
        return None

    tokens = clean_title.split()
    candidate_tokens = []
    for token in tokens[:5]:
        stripped = token.strip("()[]{}'\"“”‘’,.:;!?+-/")
        folded_token = stripped.casefold()
        if not stripped:
            break
        if starts_like_proper_name(stripped) or folded_token in BRAND_SUFFIXES:
            candidate_tokens.append(stripped)
            continue
        break

    if not candidate_tokens:
        return None

    # One-token brands are accepted only when they look brand-like, not like an
    # ordinary sentence-start word. Multi-token names need at least two proper tokens.
    candidate = " ".join(candidate_tokens).strip()
    if len(candidate_tokens) == 1:
        token = candidate_tokens[0]
        brand_like = any(ch.isupper() for ch in token[1:]) or token.isupper() or len(token) >= 7
        if not brand_like:
            return None

    if candidate.casefold() in GENERIC_TITLE_STARTS:
        return None
    if len(candidate) < 3 or len(candidate) > 64:
        return None
    if candidate.casefold() not in clean_desc.casefold():
        return None
    return candidate


def append_event(output: list[dict], source: dict, entity: dict, family: str, title: str,
                 description: str, link: str, published: datetime, captured_at: datetime,
                 entity_origin: str) -> None:
    entity_id = str(entity.get("id"))
    output.append({
        "id": item_id(source["id"], entity_id, link, title),
        "event_signature": signature(entity_id, family, title),
        "entity_id": entity_id,
        "entity_label": entity.get("label"),
        "entity_type": entity.get("entity_type"),
        "entity_origin": entity_origin,
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

        family = classify(text)
        if not family:
            continue

        matched_known = []
        for entity in registry:
            aliases = entity.get("aliases") or []
            if aliases and alias_match(text, aliases):
                matched_known.append(entity)
                append_event(
                    output, source, entity, family, title, description, link, published,
                    captured_at, "curated_registry"
                )

        auto_label = extract_title_entity(title, description)
        if auto_label and not any(alias_match(auto_label, x.get("aliases") or []) for x in matched_known):
            already_known = next(
                (x for x in registry if alias_match(auto_label, x.get("aliases") or [])),
                None,
            )
            if not already_known:
                auto_entity = {
                    "id": auto_entity_id(auto_label),
                    "label": auto_label,
                    "entity_type": "auto_discovered_organization",
                }
                append_event(
                    output, source, auto_entity, family, title, description, link, published,
                    captured_at, "auto_discovered"
                )

    return output, None


def merge_history(old: dict, fresh: list[dict], captured_at: datetime) -> dict:
    items = {str(x.get("id")): dict(x) for x in old.get("events", []) if isinstance(x, dict) and x.get("id")}
    refresh_fields = (
        "event_signature", "entity_id", "entity_label", "entity_type", "entity_origin", "family", "title",
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
    return {"version": 2, "updated_at": captured_at.isoformat(), "events": rows[:MAX_HISTORY]}


def build_auto_entities(recent: list[dict]) -> list[dict]:
    stats = {}
    for event in recent:
        if event.get("entity_origin") != "auto_discovered":
            continue
        key = str(event.get("entity_id"))
        row = stats.setdefault(key, {
            "id": key,
            "label": event.get("entity_label"),
            "entity_type": "auto_discovered_organization",
            "aliases": [event.get("entity_label")],
            "recent_events": 0,
            "families": set(),
            "publishers": set(),
        })
        row["recent_events"] += 1
        if event.get("family"):
            row["families"].add(event.get("family"))
        if event.get("publisher"):
            row["publishers"].add(event.get("publisher"))

    output = []
    for row in stats.values():
        output.append({
            "id": row["id"],
            "label": row["label"],
            "entity_type": row["entity_type"],
            "aliases": [x for x in row["aliases"] if x],
            "recent_events": row["recent_events"],
            "families": sorted(row["families"]),
            "publishers": sorted(row["publishers"]),
            "candidate_status": "needs_repeat_or_primary_verification",
        })
    output.sort(key=lambda x: (x["recent_events"], len(x["families"]), len(x["publishers"])), reverse=True)
    return output


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

    auto_entities = build_auto_entities(recent)
    payload = {
        "meta": {
            "version": "2.7.0",
            "generated_at": now.isoformat(),
            "mode": "open_world_economic_entity_discovery",
            "principle": "known_registry_normalizes_aliases_but_unknown_entities_can_enter_as_conservative_candidates"
        },
        "coverage": {
            "sources": len(SOURCES),
            "healthy_sources": sum(1 for x in health if x.get("status") == "ok"),
            "recent_events": len(recent),
            "entities_seen_recently": len(counts),
            "auto_discovered_entities": len(auto_entities),
            "history_events": len(merged.get("events", [])),
        },
        "source_health": health,
        "entity_counts": [
            {"entity_id": key, "recent_events": value}
            for key, value in sorted(counts.items(), key=lambda x: x[1], reverse=True)
        ],
        "auto_entities": auto_entities[:100],
        "events": recent[:500],
        "warnings": [
            "Media headline chỉ là discovery trigger; không phải bằng chứng cuối cùng.",
            "Auto-discovered entity chỉ là candidate tên tổ chức; không tự động được coi là quan trọng.",
            "Nhiều báo có thể đưa cùng một sự kiện; Entity Convergence phải ưu tiên evidence family chứ không đếm headline thô.",
            "Không suy ra cơ hội đầu tư/kinh doanh chỉ vì một entity xuất hiện nhiều trên báo."
        ]
    }
    write(OUTPUT, payload)
    print(
        f"entity-media healthy={payload['coverage']['healthy_sources']}/{len(SOURCES)} "
        f"recent={len(recent)} entities={len(counts)} auto={len(auto_entities)}"
    )


if __name__ == "__main__":
    main()
