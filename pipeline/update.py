#!/usr/bin/env python3
"""Opportunity Intelligence OS collector + deterministic Change Detector.

V1.2 separates four things that must not be confused:
1) raw evidence discovered from public sources;
2) normalized candidate events worth counting;
3) historical baselines and deterministic change detection;
4) curated opportunity hypotheses in data/radar.json.

The collector is deliberately conservative. Static reference pages, stale records and
administrative boilerplate remain visible in the raw feed when useful, but they do
not enter the trend baseline. This prevents the system from becoming confidently
wrong merely because one website has many matching menu links.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "pipeline" / "config.json"
RAW_PATH = ROOT / "data" / "raw_feed.json"
HISTORY_PATH = ROOT / "data" / "history.json"
INTELLIGENCE_PATH = ROOT / "data" / "intelligence.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
UA = "Mozilla/5.0 (compatible; OpportunityIntelligenceOS/1.2; +https://github.com/)"

HISTORY_EVENT_LIMIT = 5000
SNAPSHOT_LIMIT = 720
RAW_FEED_LIMIT = 1000
MIN_HISTORY_DAYS = 14
RECENT_DAYS = 7
BASELINE_DAYS = 21

REFERENCE_MARKERS = (
    "cổng thông tin quốc gia",
    "phí, lệ phí",
    "phí lệ phí",
    "hướng dẫn sử dụng",
    "hướng dẫn đăng ký",
    "công khai dự toán ngân sách",
    "công khai quyết toán ngân sách",
    "quyết toán ngân sách",
    "ngắt kết nối",
    "bảo trì hệ thống",
    "chức năng nhiệm vụ",
    "giới thiệu",
    "tập huấn",
)

GENERIC_REFERENCE_TITLES = {
    "tình hình đăng ký doanh nghiệp",
    "cổng thông tin quốc gia về đăng ký doanh nghiệp",
    "trung tâm thông tin doanh nghiệp, kinh tế tập thể, hộ kinh doanh",
}

EVENT_RULES = (
    ("procurement", (
        "đấu thầu", "mời thầu", "gói thầu", "trúng thầu", "lựa chọn nhà thầu",
    )),
    ("hiring", (
        "tuyển dụng", "tuyển nhân sự", "tuyển lao động", "việc làm",
    )),
    ("capex_expansion", (
        "mở rộng nhà máy", "nhà máy mới", "khởi công nhà máy", "tăng công suất",
        "mở rộng công suất", "xây dựng nhà máy", "xây dựng trung tâm dữ liệu",
        "đầu tư trung tâm dữ liệu", "mở rộng khu công nghiệp", "xây dựng khu công nghiệp",
    )),
    ("infrastructure_delivery", (
        "khởi công", "khánh thành", "vận hành", "khai thác", "hoàn thành",
        "thông xe", "đưa vào sử dụng",
    )),
    ("capital_flow", (
        "fdi", "vốn đầu tư nước ngoài", "thu hút đầu tư nước ngoài",
        "vốn đăng ký", "vốn thực hiện", "giải ngân", "góp vốn mua cổ phần",
    )),
    ("policy_regulation", (
        "nghị quyết", "nghị định", "quy hoạch", "phê duyệt", "quy định",
        "luật", "chính sách", "cơ chế", "thông tư",
    )),
    ("business_formation", (
        "đăng ký doanh nghiệp", "thành lập doanh nghiệp", "doanh nghiệp thành lập",
        "hộ kinh doanh", "giải thể", "tạm ngừng kinh doanh",
    )),
    ("market_data", (
        "báo cáo", "thống kê", "tình hình", "chỉ số", "tăng", "giảm",
    )),
)

GEO_ALIASES = {
    "Hà Nội": ("hà nội",),
    "TP.HCM": ("tp.hcm", "tp hcm", "thành phố hồ chí minh", "hồ chí minh"),
    "Hải Phòng": ("hải phòng",),
    "Đà Nẵng": ("đà nẵng",),
    "Cần Thơ": ("cần thơ",),
    "Huế": ("thành phố huế", "tp huế", "huế"),
    "Quảng Ninh": ("quảng ninh",),
    "Cao Bằng": ("cao bằng",),
    "Lạng Sơn": ("lạng sơn",),
    "Lai Châu": ("lai châu",),
    "Điện Biên": ("điện biên",),
    "Sơn La": ("sơn la",),
    "Tuyên Quang": ("tuyên quang",),
    "Lào Cai": ("lào cai",),
    "Thái Nguyên": ("thái nguyên",),
    "Phú Thọ": ("phú thọ",),
    "Bắc Ninh": ("bắc ninh",),
    "Hưng Yên": ("hưng yên",),
    "Ninh Bình": ("ninh bình",),
    "Thanh Hóa": ("thanh hóa",),
    "Nghệ An": ("nghệ an",),
    "Hà Tĩnh": ("hà tĩnh",),
    "Quảng Trị": ("quảng trị",),
    "Quảng Ngãi": ("quảng ngãi",),
    "Gia Lai": ("gia lai",),
    "Khánh Hòa": ("khánh hòa",),
    "Lâm Đồng": ("lâm đồng",),
    "Đắk Lắk": ("đắk lắk", "đắc lắc"),
    "Đồng Nai": ("đồng nai", "long thành"),
    "Tây Ninh": ("tây ninh",),
    "Vĩnh Long": ("vĩnh long",),
    "Đồng Tháp": ("đồng tháp",),
    "Cà Mau": ("cà mau",),
    "An Giang": ("an giang",),
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
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": UA})
    return session


SESSION = build_session()


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


def clean_href(raw_href: str) -> str:
    return re.sub(r"[\r\n\t]+", "", raw_href or "").strip()


def canonical_url(value: str) -> str:
    cleaned = clean_href(value)
    try:
        parsed = urlparse(cleaned)
        host = (parsed.netloc or "").lower()
        path = re.sub(r"/{2,}", "/", parsed.path or "/")
        if path != "/":
            path = path.rstrip("/")
        query = parsed.query or ""
        return f"{host}{path}{'?' + query if query else ''}"
    except Exception:
        return cleaned.lower()


def event_id(title: str, url: str) -> str:
    identity = f"{norm(title).casefold()}|{canonical_url(url)}"
    return hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16]


def keyword_matches(text: str, keyword: str) -> bool:
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


def source_url_allowed(src: dict, href: str) -> bool:
    required = src.get("include_url_contains") or []
    return not required or any(fragment in href for fragment in required)


def infer_event_type(title: str, categories: list[str]) -> str:
    lowered = norm(title).lower()
    for event_type, phrases in EVENT_RULES:
        if any(keyword_matches(lowered, phrase) for phrase in phrases):
            if event_type == "infrastructure_delivery" and "infrastructure" not in categories:
                continue
            return event_type
    return "other"


def infer_geography(title: str) -> list[str]:
    lowered = norm(title).lower()
    found = []
    for canonical, aliases in GEO_ALIASES.items():
        if any(keyword_matches(lowered, alias) for alias in aliases):
            found.append(canonical)
    return found[:4]


def infer_years(title: str) -> list[int]:
    return sorted({int(x) for x in re.findall(r"(?<!\d)(20\d{2})(?!\d)", title)})


def normalize_signal(item: dict, captured_at: datetime) -> dict:
    title = norm(item.get("title", ""))
    lowered = title.lower()
    categories = classify(title)
    event_type = infer_event_type(title, categories)
    geography = infer_geography(title)
    years = infer_years(title)

    quality = "candidate"
    reason = "Có trigger kinh tế/xã hội cụ thể phù hợp taxonomy hiện tại."

    if item.get("status") == "verified-seed":
        quality = "curated"
        reason = "Tín hiệu seed đã được kiểm chứng thủ công."
    elif not categories:
        quality = "noise"
        reason = "Không còn khớp taxonomy hiện tại."
    elif lowered in GENERIC_REFERENCE_TITLES:
        quality = "reference"
        reason = "Trang/menu tổng quát, không phải một sự kiện mới."
    elif any(marker in lowered for marker in REFERENCE_MARKERS):
        quality = "reference"
        reason = "Nội dung hành chính/hướng dẫn; giữ để tham chiếu nhưng không tính trend."
    elif years and max(years) < captured_at.year:
        quality = "reference"
        reason = f"Nội dung nhắc năm {max(years)}, cũ hơn năm quan sát {captured_at.year}."
    elif event_type == "other":
        quality = "reference"
        reason = "Có từ khóa ngành nhưng chưa có trigger đủ cụ thể để tính vào baseline."

    return {
        **item,
        "categories": categories or item.get("categories", []),
        "event_type": event_type,
        "signal_quality": quality,
        "quality_reason": reason,
        "geography": geography,
        "mentioned_years": years,
    }


def fetch_source(src: dict, captured_at: datetime) -> tuple[list[dict], str | None]:
    try:
        response = SESSION.get(src["url"], timeout=(10, 30))
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
        if urlparse(href).netloc != host or not source_url_allowed(src, href):
            continue

        categories = classify(title)
        if not categories:
            continue

        key = event_id(title, href)
        if key in seen:
            continue
        seen.add(key)

        raw = {
            "id": key,
            "source_id": src["id"],
            "publisher": src["name"],
            "title": title,
            "url": href,
            "categories": categories,
            "authority": src["authority"],
            "status": "unverified-headline",
        }
        items.append(normalize_signal(raw, captured_at))

    return items[:60], None


def clean_stored_item(item: dict, captured_at: datetime) -> dict | None:
    if not item.get("id") or not item.get("title"):
        return None
    cleaned = dict(item)
    cleaned["url"] = clean_href(cleaned.get("url", ""))
    if cleaned.get("status") != "verified-seed":
        categories = classify(cleaned.get("title", ""))
        if not categories:
            return None
        cleaned["categories"] = categories
        cleaned["id"] = event_id(cleaned["title"], cleaned["url"])
    return normalize_signal(cleaned, captured_at)


def earlier_timestamp(a: str | None, b: str | None) -> str | None:
    pairs = [(parse_dt(a), a), (parse_dt(b), b)]
    valid = [(dt, raw) for dt, raw in pairs if dt is not None]
    if not valid:
        return a or b
    return min(valid, key=lambda x: x[0])[1]


def later_timestamp(a: str | None, b: str | None) -> str | None:
    pairs = [(parse_dt(a), a), (parse_dt(b), b)]
    valid = [(dt, raw) for dt, raw in pairs if dt is not None]
    if not valid:
        return a or b
    return max(valid, key=lambda x: x[0])[1]


def merge_duplicate(existing: dict, incoming: dict) -> dict:
    first_a = existing.get("first_seen_at") or existing.get("collected_at")
    first_b = incoming.get("first_seen_at") or incoming.get("collected_at")
    first_seen = earlier_timestamp(first_a, first_b)
    last_seen = later_timestamp(existing.get("last_seen_at"), incoming.get("last_seen_at"))
    return {
        **existing,
        **incoming,
        "first_seen_at": first_seen,
        "collected_at": earlier_timestamp(
            existing.get("collected_at"), incoming.get("collected_at")
        ) or first_seen,
        "last_seen_at": last_seen,
    }


def merge_feed(
    old_items: list[dict],
    fetched_items: list[dict],
    captured_at: datetime,
) -> tuple[list[dict], list[dict]]:
    merged = {}
    for old_item in old_items:
        cleaned = clean_stored_item(old_item, captured_at)
        if not cleaned:
            continue
        if cleaned["id"] in merged:
            merged[cleaned["id"]] = merge_duplicate(merged[cleaned["id"]], cleaned)
        else:
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
    rows.sort(
        key=lambda x: x.get("first_seen_at") or x.get("collected_at") or "",
        reverse=True,
    )
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
        "event_type": item.get("event_type", "other"),
        "signal_quality": item.get("signal_quality", "reference"),
        "quality_reason": item.get("quality_reason"),
        "geography": item.get("geography", []),
        "mentioned_years": item.get("mentioned_years", []),
        "first_seen_at": item.get("first_seen_at") or item.get("collected_at"),
    }


def clean_history_event(event: dict, captured_at: datetime) -> dict | None:
    if not event.get("id") or not event.get("title"):
        return None
    normalized = normalize_signal(dict(event), captured_at)
    if normalized.get("status") != "verified-seed":
        categories = classify(normalized.get("title", ""))
        if not categories:
            return None
        normalized["id"] = event_id(normalized["title"], normalized.get("url", ""))
    return event_from_item(normalized)


def update_history(
    history: dict,
    feed_items: list[dict],
    new_items: list[dict],
    captured_at: datetime,
    errors: list[str],
) -> dict:
    events_by_id = {}
    for event in history.get("events", []):
        cleaned = clean_history_event(event, captured_at)
        if not cleaned:
            continue
        if cleaned["id"] in events_by_id:
            events_by_id[cleaned["id"]] = merge_duplicate(events_by_id[cleaned["id"]], cleaned)
        else:
            events_by_id[cleaned["id"]] = cleaned

    for item in feed_items:
        current = event_from_item(item)
        if current["id"] in events_by_id:
            events_by_id[current["id"]] = merge_duplicate(events_by_id[current["id"]], current)
        else:
            events_by_id[current["id"]] = current

    events = list(events_by_id.values())
    events.sort(key=lambda x: x.get("first_seen_at") or "", reverse=True)
    events = events[:HISTORY_EVENT_LIMIT]

    category_counts = defaultdict(int)
    source_counts = defaultdict(int)
    event_type_counts = defaultdict(int)
    candidate_count = 0

    for item in new_items:
        source_counts[item.get("source_id") or "unknown"] += 1
        if item.get("signal_quality") == "candidate":
            candidate_count += 1
            event_type_counts[item.get("event_type", "other")] += 1
            for category in item.get("categories", []):
                category_counts[category] += 1

    snapshots = list(history.get("snapshots", []))
    snapshots.append({
        "captured_at": iso(captured_at),
        "new_items": len(new_items),
        "new_candidates": candidate_count,
        "new_by_category": dict(sorted(category_counts.items())),
        "new_by_event_type": dict(sorted(event_type_counts.items())),
        "new_by_source": dict(sorted(source_counts.items())),
        "total_events": len(events),
        "source_errors": len(errors),
    })
    snapshots = snapshots[-SNAPSHOT_LIMIT:]

    return {
        "version": 2,
        "updated_at": iso(captured_at),
        "events": events,
        "snapshots": snapshots,
    }


def history_span_days(events: list[dict], captured_at: datetime) -> int:
    dates = [
        parse_dt(event.get("first_seen_at"))
        for event in events
        if event.get("status") != "verified-seed"
        and event.get("signal_quality") == "candidate"
    ]
    dates = [dt for dt in dates if dt is not None]
    if not dates:
        return 0
    oldest = min(dates)
    return max(1, (captured_at - oldest).days + 1)


def category_change_stats(
    events: list[dict],
    captured_at: datetime,
    history_days: int,
) -> list[dict]:
    eligible = [
        event for event in events
        if event.get("status") != "verified-seed"
        and event.get("signal_quality") == "candidate"
        and parse_dt(event.get("first_seen_at"))
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
        source_diversity = len({
            e.get("source_id") for e in recent_events if e.get("source_id")
        })

        if history_days < MIN_HISTORY_DAYS:
            trend = "warming_up"
            delta_pct = None
        elif expected_7d < 1 and recent_count >= 5:
            trend = "emerging" if source_diversity >= 2 else "single_source_spike"
            delta_pct = None
        elif expected_7d >= 2:
            ratio = recent_count / expected_7d if expected_7d else 0
            absolute_gap = recent_count - expected_7d
            if ratio >= 1.5 and absolute_gap >= 2:
                trend = "accelerating" if source_diversity >= 2 else "single_source_spike"
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
        if recent_count > 0 and source_diversity < 2:
            confidence = min(confidence, 55)

        if history_days < MIN_HISTORY_DAYS:
            explanation = (
                f"Đang học baseline: mới có {history_days}/{MIN_HISTORY_DAYS} ngày "
                "candidate events. Chưa kết luận xu hướng."
            )
        elif trend == "accelerating":
            explanation = (
                f"7 ngày gần nhất có {recent_count} candidate events từ "
                f"{source_diversity} nguồn; baseline quy đổi 7 ngày là {expected_7d:.1f}."
            )
        elif trend == "cooling":
            explanation = (
                f"Tần suất candidate events giảm: {recent_count} trong 7 ngày "
                f"so với baseline {expected_7d:.1f}."
            )
        elif trend == "emerging":
            explanation = (
                f"Xuất hiện {recent_count} candidate events từ {source_diversity} nguồn "
                "trong 7 ngày trong khi baseline trước đó gần như trống."
            )
        elif trend == "single_source_spike":
            explanation = (
                f"Tần suất tăng nhưng mới tập trung ở {source_diversity} nguồn. "
                "Đây là cảnh báo điều tra, chưa phải trend đa nguồn."
            )
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
        "accelerating": 6,
        "emerging": 5,
        "single_source_spike": 4,
        "stable": 3,
        "cooling": 2,
        "insufficient_sample": 1,
        "warming_up": 0,
    }
    results.sort(
        key=lambda x: (
            priority.get(x["trend"], 0),
            x["confidence"],
            x["recent_7d"],
        ),
        reverse=True,
    )
    return results


def build_intelligence(history: dict, captured_at: datetime, errors: list[str]) -> dict:
    events = history.get("events", [])
    history_days = history_span_days(events, captured_at)
    changes = category_change_stats(events, captured_at, history_days)

    recent_24h_cutoff = captured_at - timedelta(hours=24)
    candidate_events = [
        event for event in events
        if event.get("status") != "verified-seed"
        and event.get("signal_quality") == "candidate"
    ]
    reference_events = [
        event for event in events
        if event.get("status") != "verified-seed"
        and event.get("signal_quality") == "reference"
    ]

    top_new_events = []
    for event in candidate_events:
        seen_at = parse_dt(event.get("first_seen_at"))
        if seen_at and seen_at >= recent_24h_cutoff:
            top_new_events.append(event)
    top_new_events.sort(key=lambda x: x.get("first_seen_at") or "", reverse=True)
    top_new_events = top_new_events[:20]

    event_types_7d = Counter()
    geographies_7d = Counter()
    recent_cutoff = captured_at - timedelta(days=7)
    for event in candidate_events:
        seen_at = parse_dt(event.get("first_seen_at"))
        if not seen_at or seen_at < recent_cutoff:
            continue
        event_types_7d[event.get("event_type", "other")] += 1
        for geo in event.get("geography", []):
            geographies_7d[geo] += 1

    status = "active" if history_days >= MIN_HISTORY_DAYS else "warming_up"
    warnings = []
    if status == "warming_up":
        warnings.append(
            f"Change Detector đang học baseline ({history_days}/{MIN_HISTORY_DAYS} ngày). "
            "Chỉ candidate events mới được tính; chưa coi chênh lệch hiện tại là trend."
        )
    if errors:
        warnings.append(
            f"Có {len(errors)} nguồn lỗi ở lần thu thập gần nhất; độ phủ dữ liệu bị giảm."
        )

    unique_sources = {
        event.get("source_id") for event in candidate_events if event.get("source_id")
    }

    return {
        "meta": {
            "generated_at": iso(captured_at),
            "status": status,
            "history_days": history_days,
            "required_history_days": MIN_HISTORY_DAYS,
            "recent_window_days": RECENT_DAYS,
            "baseline_window_days": BASELINE_DAYS,
            "method": "normalized_candidate_frequency_change_v2",
        },
        "category_changes": changes,
        "top_new_events": top_new_events,
        "event_types_7d": dict(event_types_7d.most_common()),
        "geographies_7d": dict(geographies_7d.most_common(15)),
        "coverage": {
            "historical_events": len(events),
            "candidate_events": len(candidate_events),
            "reference_events": len(reference_events),
            "unique_candidate_sources": len(unique_sources),
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
        items, error = fetch_source(source, captured_at)
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

    old_history = load_json(
        HISTORY_PATH,
        {"version": 2, "events": [], "snapshots": []},
    )
    history = update_history(old_history, feed_rows, new_items, captured_at, errors)
    write_json(HISTORY_PATH, history)

    intelligence = build_intelligence(history, captured_at, errors)
    write_json(INTELLIGENCE_PATH, intelligence)

    coverage = intelligence["coverage"]
    print(
        f"saved feed={len(feed_rows)} new={len(new_items)} "
        f"history={len(history['events'])} candidates={coverage['candidate_events']} "
        f"references={coverage['reference_events']} status={intelligence['meta']['status']} "
        f"errors={len(errors)}"
    )
    for error in errors:
        print(error, file=sys.stderr)


if __name__ == "__main__":
    main()
