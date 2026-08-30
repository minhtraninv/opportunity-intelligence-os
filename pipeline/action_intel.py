#!/usr/bin/env python3
"""V1.3 Action Intelligence: procurement-first buyer trigger radar.

This module deliberately separates discovery from verification.
It collects public tender-list metadata, keeps first-seen history, scores
small-capital investigation fit, and outputs buyer triggers. A discovery result is
never treated as a verified opportunity until the tender code is checked on the
National E-Procurement System and the actual package requirements are reviewed.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "pipeline" / "action_sources.json"
HISTORY_PATH = ROOT / "data" / "action_history.json"
OUTPUT_PATH = ROOT / "data" / "action_intelligence.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

VN_TZ = timezone(timedelta(hours=7))
UA = "Mozilla/5.0 (compatible; OpportunityIntelligenceOS/1.3; +https://github.com/)"
HISTORY_LIMIT = 2500
ACTIVE_LIMIT = 80

CATEGORY_RULES = (
    ("digital_services", ("phần mềm", "website", "hệ thống thông tin", "công nghệ thông tin", "chuyển đổi số", "bảo trì phần mềm", "dịch vụ it", "số hóa", "gis")),
    ("printing_media", ("in ấn", "in báo", "in tài liệu", "truyền thông", "quảng cáo", "thiết kế", "ấn phẩm")),
    ("consulting", ("tư vấn", "lập quy hoạch", "khảo sát", "giám sát", "thẩm tra", "lập hồ sơ")),
    ("maintenance", ("bảo trì", "bảo dưỡng", "sửa chữa", "vệ sinh", "kiểm định")),
    ("office_goods", ("văn phòng phẩm", "máy tính", "máy in", "thiết bị văn phòng", "bàn ghế", "mực in")),
    ("garment_ppe", ("đồ vải", "đồng phục", "bảo hộ lao động", "ppe", "quần áo", "giày bảo hộ")),
    ("food_services", ("thực phẩm", "suất ăn", "catering", "nước uống", "đồ ăn", "bếp ăn")),
    ("logistics", ("vận chuyển", "vận tải", "logistics", "giao nhận", "thuê xe", "kho bãi")),
    ("medical", ("thuốc", "y tế", "dược", "xét nghiệm", "vật tư y tế", "thiết bị y tế")),
    ("machinery", ("máy móc", "thiết bị", "phụ tùng", "máy may", "máy nén", "cẩu điện")),
    ("construction", ("thi công", "xây dựng", "xây lắp", "công trình", "cầu", "đường", "hạ tầng")),
)

FIT = {
    "digital_services": 86,
    "printing_media": 84,
    "consulting": 76,
    "maintenance": 74,
    "office_goods": 70,
    "garment_ppe": 68,
    "food_services": 62,
    "logistics": 60,
    "medical": 38,
    "machinery": 30,
    "construction": 22,
    "other": 45,
}

ANGLES = {
    "digital_services": ["Dịch vụ triển khai/maintain ngách", "Làm thầu phụ cho đơn vị IT lớn hơn", "Đóng gói hỗ trợ vận hành sau triển khai"],
    "printing_media": ["In/thiết kế theo đơn", "Kết nối xưởng in và hưởng biên dịch vụ", "Nhận hạng mục nhỏ hoặc làm thầu phụ"],
    "consulting": ["Tìm chuyên gia/đối tác đủ năng lực để liên danh", "Nhận phần khảo sát, hồ sơ hoặc triển khai phụ trợ", "Lead generation B2B cho đơn vị tư vấn"],
    "maintenance": ["Bảo trì định kỳ", "Vệ sinh/facility", "Sourcing vật tư thay thế", "Làm thầu phụ theo địa bàn"],
    "office_goods": ["Sourcing hàng theo yêu cầu", "Đại lý/phân phối theo đơn", "Ghép nhà cung cấp và giao hàng"],
    "garment_ppe": ["Sourcing xưởng may", "Đồng phục/PPE theo đơn", "Thầu phụ sản xuất hoặc giao hàng"],
    "food_services": ["Cung ứng thực phẩm/suất ăn theo địa bàn", "Kết nối bếp/xưởng có năng lực", "Nhận phần giao vận"],
    "logistics": ["Ghép nhà xe/kho phù hợp", "Điều phối giao nhận", "Nhận tuyến nhỏ hoặc làm thầu phụ"],
    "medical": ["Chỉ điều tra nếu đã có pháp lý/phân phối phù hợp", "Tìm distributor đủ điều kiện", "Không ôm hàng trước khi xác minh điều kiện"],
    "machinery": ["Tìm đại lý/nhà sản xuất", "Làm sourcing/giới thiệu", "Tránh ôm thiết bị nếu chưa có đơn chắc chắn"],
    "construction": ["Tìm hạng mục thầu phụ nhỏ", "Cung ứng vật tư/dịch vụ phụ trợ", "Không tham gia tổng thầu nếu năng lực tài chính không phù hợp"],
    "other": ["Xác minh phạm vi rồi tìm hạng mục nhỏ có thể thầu phụ", "Sourcing/lead generation thay vì ôm vốn", "Chỉ bỏ vốn sau khi có buyer rõ"],
}


def session() -> requests.Session:
    retry = Retry(total=2, connect=2, read=2, status=2, backoff_factor=0.8,
                  status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=frozenset({"GET"}), raise_on_status=False)
    s = requests.Session()
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({"User-Agent": UA, "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.7"})
    return s


SESSION = session()


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def parse_vn_datetime(text: str) -> datetime | None:
    m = re.search(r"(?:(\d{1,2}):(\d{2})\s+)?(\d{1,2})/(\d{1,2})/(20\d{2})", text or "")
    if not m:
        return None
    hh = int(m.group(1) or 0)
    mm = int(m.group(2) or 0)
    try:
        return datetime(int(m.group(5)), int(m.group(4)), int(m.group(3)), hh, mm, tzinfo=VN_TZ).astimezone(timezone.utc)
    except ValueError:
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


def classify(title: str) -> str:
    t = title.casefold()
    for category, phrases in CATEGORY_RULES:
        if any(phrase.casefold() in t for phrase in phrases):
            return category
    return "other"


def clean_owner(value: str) -> str:
    value = norm(value)
    value = re.sub(r"^vn\d+\s+", "", value, flags=re.I)
    return value


def parse_tender_source(src: dict, captured_at: datetime) -> tuple[list[dict], str | None]:
    try:
        r = SESSION.get(src["url"], timeout=(10, 30))
        r.raise_for_status()
    except Exception as exc:
        return [], f"{src['name']}: {type(exc).__name__}: {exc}"

    soup = BeautifulSoup(r.text, "html.parser")
    rows = []
    seen = set()

    for tr in soup.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 4:
            continue

        package_text = norm(cells[0].get_text(" ", strip=True))
        code_match = re.search(r"\bIB\d{8,}-\d{2}\b", package_text, flags=re.I)
        if not code_match:
            continue
        code = code_match.group(0).upper()
        if code in seen:
            continue
        seen.add(code)

        title = norm(package_text.replace(code_match.group(0), "", 1))
        if len(title) < 8:
            continue

        owner = clean_owner(cells[1].get_text(" ", strip=True))
        posted_at = parse_vn_datetime(cells[2].get_text(" ", strip=True))
        closes_at = parse_vn_datetime(cells[3].get_text(" ", strip=True))
        anchor = cells[0].find("a", href=True)
        detail_url = urljoin(src["url"], anchor["href"]) if anchor else src["url"]
        category = classify(title)

        days_to_close = None
        if closes_at:
            days_to_close = round((closes_at - captured_at).total_seconds() / 86400, 1)

        rows.append({
            "id": code,
            "tender_code": code,
            "title": title,
            "buyer": owner or "Chưa xác định",
            "posted_at": iso(posted_at) if posted_at else None,
            "closes_at": iso(closes_at) if closes_at else None,
            "days_to_close": days_to_close,
            "procurement_category": category,
            "source_id": src["id"],
            "source_name": src["name"],
            "source_url": detail_url,
            "authority": src.get("authority", 0.5),
            "discovery_only": bool(src.get("discovery_only", True)),
            "direct_private": bool(src.get("direct_private", False)),
            "first_seen_at": iso(captured_at),
            "last_seen_at": iso(captured_at),
        })

    if not rows:
        return [], f"{src['name']}: không đọc được dòng gói thầu từ HTML hiện tại"
    return rows[:80], None


def merge_history(old: dict, fresh: list[dict], captured_at: datetime) -> dict:
    by_id = {x["id"]: dict(x) for x in old.get("items", []) if x.get("id")}
    for item in fresh:
        previous = by_id.get(item["id"])
        if previous:
            sources = sorted(set(previous.get("source_ids", [previous.get("source_id")]) + [item.get("source_id")]) - {None})
            by_id[item["id"]] = {
                **previous,
                **item,
                "first_seen_at": previous.get("first_seen_at") or item["first_seen_at"],
                "last_seen_at": iso(captured_at),
                "source_ids": sources,
                "direct_private": bool(previous.get("direct_private") or item.get("direct_private")),
                "authority": max(float(previous.get("authority", 0)), float(item.get("authority", 0))),
            }
        else:
            item["source_ids"] = [item.get("source_id")]
            by_id[item["id"]] = item

    items = list(by_id.values())
    items.sort(key=lambda x: x.get("posted_at") or x.get("first_seen_at") or "", reverse=True)
    return {"version": 1, "updated_at": iso(captured_at), "items": items[:HISTORY_LIMIT]}


def score_trigger(item: dict, captured_at: datetime) -> dict:
    category = item.get("procurement_category", "other")
    fit = FIT.get(category, 45)
    score = 30 + round(float(item.get("authority", 0.5)) * 20)
    if item.get("buyer") and item.get("buyer") != "Chưa xác định":
        score += 10
    if item.get("tender_code"):
        score += 8
    if item.get("direct_private"):
        score += 5

    closes_at = None
    try:
        if item.get("closes_at"):
            closes_at = datetime.fromisoformat(item["closes_at"].replace("Z", "+00:00"))
    except ValueError:
        closes_at = None

    days = round((closes_at - captured_at).total_seconds() / 86400, 1) if closes_at else item.get("days_to_close")
    if days is not None:
        if 5 <= days <= 21:
            score += 10
        elif 2 <= days < 5:
            score += 5
        elif days < 0:
            score -= 30

    score += round(fit * 0.22)
    score = max(0, min(95, score))

    if days is not None and days < 0:
        action_level = "closed"
    elif days is not None and days < 2:
        action_level = "too_late"
    elif score >= 72 and (days is None or days <= 21):
        action_level = "investigate_now"
    elif score >= 58:
        action_level = "watch"
    else:
        action_level = "context"

    return {
        **item,
        "days_to_close": days,
        "small_capital_fit_score": fit,
        "buyer_trigger_score": score,
        "action_level": action_level,
        "small_capital_angles": ANGLES.get(category, ANGLES["other"]),
        "verification_required": True,
        "official_verification_url": CONFIG["official_verification"]["url"],
        "next_action": (
            f"Tra mã {item.get('tender_code')} trên Hệ thống mạng đấu thầu quốc gia; "
            "đọc giá gói, tiêu chí năng lực, bảo lãnh và phạm vi. Nếu vượt khả năng, chỉ tìm hạng mục thầu phụ/sourcing phù hợp."
        ),
        "kill_criteria": (
            "Loại nếu không xác minh được mã trên nguồn chính thức, thời hạn quá sát, "
            "yêu cầu doanh thu/bảo lãnh/pháp lý vượt khả năng, hoặc phải ôm hàng/vốn trước khi có buyer chắc chắn."
        ),
    }


def build_output(history: dict, captured_at: datetime, errors: list[str], source_health: list[dict]) -> dict:
    scored = [score_trigger(x, captured_at) for x in history.get("items", [])]
    active = [x for x in scored if x.get("action_level") not in {"closed", "too_late"}]
    active.sort(key=lambda x: (x.get("buyer_trigger_score", 0), x.get("posted_at") or ""), reverse=True)

    categories = Counter(x.get("procurement_category", "other") for x in active)
    investigate = [x for x in active if x.get("action_level") == "investigate_now"]
    direct = [x for x in active if x.get("direct_private")]

    return {
        "meta": {
            "version": "1.3",
            "generated_at": iso(captured_at),
            "mode": "procurement_action_intelligence",
            "principle": "discovery_then_official_verification",
        },
        "coverage": {
            "historical_tenders": len(history.get("items", [])),
            "active_tenders": len(active),
            "investigate_now": len(investigate),
            "direct_private_tenders": len(direct),
            "source_errors_last_run": len(errors),
        },
        "category_summary": dict(categories.most_common()),
        "source_health": source_health,
        "buyer_triggers": active[:ACTIVE_LIMIT],
        "warnings": [
            "DauThau.info chỉ được dùng để discovery; phải xác minh mã TBMT trên Hệ thống mạng đấu thầu quốc gia trước khi hành động.",
            "Small-capital fit chỉ là heuristic theo loại hàng/dịch vụ; chưa biết giá gói, bảo lãnh, doanh thu tối thiểu hay giấy phép thì chưa được coi là phù hợp vốn.",
            *([f"Có {len(errors)} nguồn lỗi ở lần chạy gần nhất."] if errors else []),
        ],
    }


def main() -> None:
    captured_at = now_utc()
    fresh = []
    errors = []
    source_health = []

    for src in CONFIG["sources"]:
        items, error = parse_tender_source(src, captured_at)
        fresh.extend(items)
        source_health.append({
            "source_id": src["id"],
            "name": src["name"],
            "items_this_run": len(items),
            "status": "error" if error else "ok",
            "error": error,
            "discovery_only": bool(src.get("discovery_only", True)),
        })
        if error:
            errors.append(error)

    old = load_json(HISTORY_PATH, {"version": 1, "items": []})
    history = merge_history(old, fresh, captured_at)
    write_json(HISTORY_PATH, history)

    output = build_output(history, captured_at, errors, source_health)
    write_json(OUTPUT_PATH, output)

    c = output["coverage"]
    print(
        f"action-intel historical={c['historical_tenders']} active={c['active_tenders']} "
        f"investigate={c['investigate_now']} direct={c['direct_private_tenders']} errors={len(errors)}"
    )
    for error in errors:
        print(error)


if __name__ == "__main__":
    main()
