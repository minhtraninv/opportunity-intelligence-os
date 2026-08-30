#!/usr/bin/env python3
"""V1.3 Procurement Action Intelligence using the website API of Mua Sam Cong.

The endpoint is used by the official National E-Procurement website, but it is not a
published/stable developer API. Therefore the collector treats schema changes as a
source-health problem and never silently invents fields.

Decision rule:
- search metadata can create a buyer trigger;
- TBMT detail confirmation upgrades metadata confidence;
- qualification / bid-security requirements remain UNVERIFIED until the actual tender
  documents are read, so "small-capital fit" is only an investigation prior.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = ROOT / "data" / "action_history.json"
OUTPUT_PATH = ROOT / "data" / "action_intelligence.json"

BASE = "https://muasamcong.mpi.gov.vn"
SEARCH_URL = BASE + "/o/egp-portal-contractor-selection-v2/services/smart/search?token=fake"
TBMT_URL = BASE + "/o/egp-portal-contractor-selection-v2/services/lcnt_tbmt_ttc_ldt?token=fake"
OFFICIAL_HOME = BASE + "/"

VN_TZ = timezone(timedelta(hours=7))
HISTORY_LIMIT = 3000
ACTIVE_LIMIT = 80
SEARCH_PAGE_SIZE = 8
MAX_DETAIL_REQUESTS = 30

SEARCH_KEYWORDS = (
    "vệ sinh", "bảo trì", "in ấn", "văn phòng phẩm", "đồng phục", "phần mềm",
    "số hóa", "thuê xe", "suất ăn", "bảo hộ lao động", "máy tính", "tư vấn",
)

CATEGORY_RULES = (
    ("digital_services", ("phần mềm", "website", "hệ thống thông tin", "công nghệ thông tin", "chuyển đổi số", "số hóa", "gis")),
    ("printing_media", ("in ấn", "in tài liệu", "in báo", "ấn phẩm", "thiết kế", "truyền thông")),
    ("consulting", ("tư vấn", "khảo sát", "giám sát", "thẩm tra", "lập hồ sơ")),
    ("maintenance", ("bảo trì", "bảo dưỡng", "sửa chữa", "vệ sinh", "kiểm định")),
    ("office_goods", ("văn phòng phẩm", "máy tính", "máy in", "mực in", "thiết bị văn phòng", "bàn ghế")),
    ("garment_ppe", ("đồng phục", "bảo hộ lao động", "ppe", "quần áo bảo hộ", "giày bảo hộ")),
    ("food_services", ("suất ăn", "thực phẩm", "catering", "nước uống", "bếp ăn")),
    ("logistics", ("thuê xe", "vận chuyển", "vận tải", "logistics", "giao nhận", "kho bãi")),
    ("medical", ("thuốc", "vật tư y tế", "thiết bị y tế", "xét nghiệm", "dược")),
    ("machinery", ("máy móc", "phụ tùng", "thiết bị công nghiệp")),
    ("construction", ("thi công", "xây dựng", "xây lắp", "công trình")),
)

FIT_PRIOR = {
    "digital_services": 88, "printing_media": 85, "consulting": 78, "maintenance": 78,
    "office_goods": 72, "garment_ppe": 70, "food_services": 63, "logistics": 62,
    "medical": 35, "machinery": 30, "construction": 20, "other": 45,
}

ANGLES = {
    "digital_services": ["Triển khai/maintain một module ngách", "Làm thầu phụ cho integrator lớn hơn", "Hỗ trợ vận hành sau triển khai"],
    "printing_media": ["In/thiết kế theo đơn", "Kết nối xưởng in và hưởng biên dịch vụ", "Nhận hạng mục nhỏ làm thầu phụ"],
    "consulting": ["Ghép chuyên gia đủ năng lực", "Nhận phần khảo sát/hồ sơ phụ trợ", "Lead generation B2B cho đơn vị tư vấn"],
    "maintenance": ["Bảo trì định kỳ", "Vệ sinh/facility", "Sourcing vật tư thay thế", "Thầu phụ theo địa bàn"],
    "office_goods": ["Sourcing theo đơn", "Ghép distributor và giao hàng", "Không ôm tồn kho trước khi có đơn chắc chắn"],
    "garment_ppe": ["Sourcing xưởng may", "Đồng phục/PPE theo đơn", "Nhận phần sản xuất/giao hàng"],
    "food_services": ["Cung ứng theo địa bàn", "Kết nối bếp/xưởng đủ điều kiện", "Nhận phần giao vận"],
    "logistics": ["Ghép nhà xe/kho", "Điều phối giao nhận", "Nhận tuyến/hạng mục nhỏ"],
    "medical": ["Chỉ điều tra nếu có đối tác đủ pháp lý", "Tìm distributor đủ điều kiện", "Không ôm hàng trước khi xác minh"],
    "machinery": ["Sourcing/giới thiệu đại lý", "Tìm phần dịch vụ lắp đặt/bảo trì", "Tránh ôm thiết bị bằng vốn cá nhân"],
    "construction": ["Tìm hạng mục thầu phụ nhỏ", "Cung ứng dịch vụ/vật tư phụ trợ", "Không coi tổng thầu là cơ hội vốn nhỏ"],
    "other": ["Đọc phạm vi rồi tìm hạng mục nhỏ", "Ưu tiên sourcing/lead generation", "Chỉ bỏ vốn sau khi buyer và điều kiện rõ"],
}


def build_session() -> requests.Session:
    retry = Retry(
        total=2, connect=2, read=2, status=2, backoff_factor=0.8,
        status_forcelist=(408, 429, 500, 502, 503, 504),
        allowed_methods=frozenset({"POST"}), raise_on_status=False,
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0", "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json; charset=utf-8", "Origin": BASE,
        "Referer": OFFICIAL_HOME, "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.7",
    })
    return session


SESSION = build_session()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def norm(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def post_json(url: str, payload, timeout: int = 28):
    response = SESSION.post(url, json=payload, timeout=(10, timeout))
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if "json" not in content_type.lower() and not response.text.lstrip().startswith(("{", "[")):
        raise ValueError(f"non-JSON response: {content_type or 'unknown'}")
    return response.json()


def walk_objects(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk_objects(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk_objects(value)


def first_value(obj: dict | None, *names):
    if not isinstance(obj, dict):
        return None
    for name in names:
        value = obj.get(name)
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if not value or value.lower() in {"undefined", "null"}:
                continue
        return value
    return None


def find_dict_with_field(node, field: str):
    for obj in walk_objects(node):
        if obj.get(field) is not None:
            return obj
    return None


def parse_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        stamp = float(value)
        if stamp > 10_000_000_000:
            stamp /= 1000
        try:
            return datetime.fromtimestamp(stamp, tz=timezone.utc)
        except Exception:
            return None
    text = norm(value)
    if not text:
        return None
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=VN_TZ)
            return dt.astimezone(timezone.utc)
        except ValueError:
            pass
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=VN_TZ).astimezone(timezone.utc)
        except ValueError:
            pass
    return None


def number_value(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    text = norm(value).replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def classify(title: str) -> str:
    lowered = norm(title).casefold()
    for category, phrases in CATEGORY_RULES:
        if any(phrase.casefold() in lowered for phrase in phrases):
            return category
    return "other"


def search_payload(keyword: str) -> list[dict]:
    return [{
        "pageSize": SEARCH_PAGE_SIZE, "pageNumber": 0,
        "query": [{
            "index": "es-contractor-selection", "keyWord": keyword, "matchType": "exact",
            "matchFields": ["notifyNo", "bidName"],
            "filters": [{"fieldName": "type", "searchType": "in", "fieldValues": ["es-notify-contractor"]}],
        }],
    }]


def search_keyword(keyword: str) -> tuple[list[dict], str | None]:
    try:
        root = post_json(SEARCH_URL, search_payload(keyword))
    except Exception as exc:
        return [], f"MSC search '{keyword}': {type(exc).__name__}: {exc}"
    matches, seen = [], set()
    for obj in walk_objects(root):
        notify_no = norm(first_value(obj, "notifyNo"))
        notify_id = norm(first_value(obj, "notifyId", "id"))
        bid_name = norm(first_value(obj, "bidName"))
        if not notify_no or not notify_id or not bid_name or notify_no in seen:
            continue
        seen.add(notify_no)
        matches.append({**obj, "_search_keyword": keyword})
    return matches[:SEARCH_PAGE_SIZE], None


def fetch_tbmt(notify_id: str):
    try:
        root = post_json(TBMT_URL, {"id": notify_id})
        main = root.get("bidoNotifyContractorM") if isinstance(root, dict) else None
        if not isinstance(main, dict):
            main = find_dict_with_field(root, "bidName")
        return main, None
    except Exception as exc:
        return None, f"TBMT {notify_id}: {type(exc).__name__}: {exc}"


def detail_url(search_obj: dict) -> str:
    params = {
        "p_p_id": "egpportalcontractorselectionv2_WAR_egpportalcontractorselectionv2",
        "p_p_lifecycle": "0", "p_p_state": "normal", "p_p_mode": "view",
        "_egpportalcontractorselectionv2_WAR_egpportalcontractorselectionv2_render": "detail-v2",
        "type": "es-notify-contractor", "stepCode": first_value(search_obj, "stepCode", "step") or "undefined",
        "id": first_value(search_obj, "id", "notifyId") or "undefined",
        "notifyId": first_value(search_obj, "notifyId", "id") or "undefined",
        "inputResultId": first_value(search_obj, "inputResultId") or "undefined",
        "bidOpenId": first_value(search_obj, "bidOpenId") or "undefined",
        "processApply": first_value(search_obj, "processApply") or "LDT",
        "bidMode": first_value(search_obj, "bidMode") or "undefined",
        "notifyNo": first_value(search_obj, "notifyNo") or "undefined",
        "planNo": first_value(search_obj, "planNo") or "undefined", "step": "tbmt",
        "isInternet": first_value(search_obj, "isInternet") or "undefined",
        "bidForm": first_value(search_obj, "bidForm") or "undefined",
    }
    return BASE + "/web/guest/contractor-selection?" + urlencode(params)


def normalize_tender(search_obj: dict, detail: dict | None, captured_at: datetime) -> dict:
    notify_no = norm(first_value(search_obj, "notifyNo") or first_value(detail, "notifyNo"))
    notify_id = norm(first_value(search_obj, "notifyId", "id") or first_value(detail, "id", "notifyId"))
    title = norm(first_value(detail, "bidName") or first_value(search_obj, "bidName"))
    buyer = norm(first_value(detail, "investorName", "procuringEntityName") or first_value(search_obj, "investorName", "procuringEntityName") or "Chưa xác định")
    posted = parse_datetime(first_value(search_obj, "publicDate", "publishDate", "createdDate") or first_value(detail, "publicDate", "publishDate", "createdDate"))
    closes = parse_datetime(first_value(detail, "bidCloseDate") or first_value(search_obj, "bidCloseDate"))
    opens = parse_datetime(first_value(detail, "bidOpenDate") or first_value(search_obj, "bidOpenDate"))
    price = number_value(first_value(detail, "bidEstimatePrice", "bidPrice") or first_value(search_obj, "bidPrice", "bidEstimatePrice"))
    days_to_close = round((closes - captured_at).total_seconds() / 86400, 1) if closes else None
    return {
        "id": notify_no, "tender_code": notify_no, "notify_id": notify_id, "title": title,
        "buyer": buyer, "posted_at": iso(posted) if posted else None, "closes_at": iso(closes) if closes else None,
        "opens_at": iso(opens) if opens else None, "days_to_close": days_to_close, "package_price_vnd": price,
        "procurement_category": classify(title), "matched_keywords": [search_obj.get("_search_keyword")],
        "source_id": "msc-official", "source_name": "Hệ thống mạng đấu thầu quốc gia",
        "source_url": detail_url(search_obj), "authority": 1.0, "official_metadata": True,
        "tbmt_detail_confirmed": bool(detail), "requirements_status": "unverified",
        "first_seen_at": iso(captured_at), "last_seen_at": iso(captured_at),
    }


def collect(captured_at: datetime) -> tuple[list[dict], list[str], list[dict]]:
    raw_matches, errors, health = [], [], []
    for keyword in SEARCH_KEYWORDS:
        matches, error = search_keyword(keyword)
        raw_matches.extend(matches)
        health.append({"keyword": keyword, "search_results": len(matches), "status": "error" if error else "ok", "error": error})
        if error:
            errors.append(error)

    by_notify = {}
    for obj in raw_matches:
        code = norm(obj.get("notifyNo"))
        if not code:
            continue
        if code in by_notify:
            kws = set(by_notify[code].get("_matched_keywords", [by_notify[code].get("_search_keyword")]))
            kws.add(obj.get("_search_keyword"))
            by_notify[code]["_matched_keywords"] = sorted(x for x in kws if x)
        else:
            obj["_matched_keywords"] = [obj.get("_search_keyword")]
            by_notify[code] = obj

    candidates = list(by_notify.values())
    candidates.sort(key=lambda x: parse_datetime(first_value(x, "publicDate", "publishDate", "createdDate")) or datetime(1970, 1, 1, tzinfo=timezone.utc), reverse=True)

    rows, detail_budget = [], MAX_DETAIL_REQUESTS
    for search_obj in candidates:
        notify_id = norm(first_value(search_obj, "notifyId", "id"))
        detail = None
        if notify_id and detail_budget > 0:
            detail, error = fetch_tbmt(notify_id)
            detail_budget -= 1
            if error:
                errors.append(error)
        row = normalize_tender(search_obj, detail, captured_at)
        row["matched_keywords"] = search_obj.get("_matched_keywords", [search_obj.get("_search_keyword")])
        rows.append(row)
    return rows, errors, health


def merge_history(old: dict, fresh: list[dict], captured_at: datetime) -> dict:
    by_id = {item["id"]: dict(item) for item in old.get("items", []) if item.get("id")}
    for item in fresh:
        previous = by_id.get(item["id"])
        if previous:
            keywords = sorted(set(previous.get("matched_keywords", []) + item.get("matched_keywords", [])))
            by_id[item["id"]] = {**previous, **item, "matched_keywords": keywords, "first_seen_at": previous.get("first_seen_at") or item["first_seen_at"], "last_seen_at": iso(captured_at)}
        else:
            by_id[item["id"]] = item
    items = list(by_id.values())
    items.sort(key=lambda x: x.get("posted_at") or x.get("first_seen_at") or "", reverse=True)
    return {"version": 2, "updated_at": iso(captured_at), "items": items[:HISTORY_LIMIT]}


def price_band(price):
    if price is None: return "unknown"
    if price <= 100_000_000: return "small"
    if price <= 500_000_000: return "medium"
    if price <= 2_000_000_000: return "large"
    return "very_large"


def score_trigger(item: dict, captured_at: datetime) -> dict:
    category = item.get("procurement_category", "other")
    fit_prior = FIT_PRIOR.get(category, 45)
    score = 38 + (15 if item.get("tbmt_detail_confirmed") else 8)
    if item.get("buyer") and item.get("buyer") != "Chưa xác định": score += 10
    if item.get("package_price_vnd") is not None: score += 5
    closes_at = parse_datetime(item.get("closes_at"))
    days = round((closes_at - captured_at).total_seconds() / 86400, 1) if closes_at else item.get("days_to_close")
    if days is not None:
        if 5 <= days <= 25: score += 10
        elif 2 <= days < 5: score += 4
        elif days < 0: score -= 35
    score += round(fit_prior * 0.18)
    band = price_band(item.get("package_price_vnd"))
    if band == "very_large" and category in {"office_goods", "garment_ppe", "food_services", "machinery", "medical"}: score -= 8
    if category in {"construction", "medical", "machinery"}: score -= 5
    score = max(0, min(95, score))
    if days is not None and days < 0: action_level = "closed"
    elif days is not None and days < 2: action_level = "too_late"
    elif score >= 72: action_level = "investigate_now"
    elif score >= 58: action_level = "watch"
    else: action_level = "context"
    return {
        **item, "days_to_close": days, "package_price_band": band,
        "small_capital_fit_score": fit_prior, "small_capital_fit_status": "prior_only_requirements_unverified",
        "buyer_trigger_score": score, "action_level": action_level,
        "small_capital_angles": ANGLES.get(category, ANGLES["other"]), "verification_required": True,
        "official_verification_url": item.get("source_url") or OFFICIAL_HOME,
        "next_action": f"Mở mã {item.get('tender_code')} trên Hệ thống mạng đấu thầu quốc gia. Đọc HSMT: bảo đảm dự thầu, doanh thu/hợp đồng tương tự, nhân sự, giấy phép và điều khoản thanh toán. Nếu prime contract vượt khả năng, tìm nhà thầu phù hợp để đề xuất sourcing/thầu phụ thay vì tự ôm vốn.",
        "kill_criteria": "Loại nếu mã không còn hiệu lực, thời hạn quá sát, yêu cầu pháp lý/doanh thu/bảo lãnh vượt khả năng, dòng tiền thanh toán khiến phải vay/ôm hàng quá mức, hoặc không tìm được vai trò thầu phụ/sourcing thực tế.",
    }


def build_output(history: dict, captured_at: datetime, errors: list[str], source_health: list[dict]) -> dict:
    scored = [score_trigger(item, captured_at) for item in history.get("items", [])]
    active = [item for item in scored if item.get("action_level") not in {"closed", "too_late"}]
    recent_cutoff = captured_at - timedelta(days=45)
    active = [item for item in active if not item.get("posted_at") or (parse_datetime(item.get("posted_at")) or recent_cutoff) >= recent_cutoff]
    active.sort(key=lambda x: (x.get("buyer_trigger_score", 0), x.get("posted_at") or ""), reverse=True)
    investigate = [item for item in active if item.get("action_level") == "investigate_now"]
    categories = Counter(item.get("procurement_category", "other") for item in active)
    confirmed = sum(bool(item.get("tbmt_detail_confirmed")) for item in active)
    return {
        "meta": {"version": "1.3.1", "generated_at": iso(captured_at), "mode": "official_msc_procurement_action_intelligence", "principle": "official_metadata_then_requirements_verification", "api_stability": "website_endpoint_not_published_developer_api"},
        "coverage": {"historical_tenders": len(history.get("items", [])), "active_recent_tenders": len(active), "tbmt_detail_confirmed": confirmed, "investigate_now": len(investigate), "source_errors_last_run": len(errors)},
        "category_summary": dict(categories.most_common()), "source_health": source_health,
        "buyer_triggers": active[:ACTIVE_LIMIT],
        "warnings": [
            "Metadata lấy từ endpoint website của Hệ thống mạng đấu thầu quốc gia; endpoint này có thể đổi schema vì không phải API developer được cam kết ổn định.",
            "Small-capital fit là prior theo loại gói, KHÔNG phải kết luận đủ năng lực. HSMT, bảo lãnh, doanh thu tương tự và điều khoản thanh toán vẫn phải kiểm tra thủ công.",
            "Không dùng giá gói thầu làm đại diện trực tiếp cho vốn cần có; có thể có cơ hội thầu phụ/sourcing, nhưng chỉ sau khi xác định được prime contractor/buyer path.",
            *([f"Có {len(errors)} lỗi request/schema trong lần chạy gần nhất; không suy diễn từ dữ liệu thiếu."] if errors else []),
        ],
    }


def main() -> None:
    captured_at = now_utc()
    fresh, errors, source_health = collect(captured_at)
    history = merge_history(load_json(HISTORY_PATH, {"version": 2, "items": []}), fresh, captured_at)
    write_json(HISTORY_PATH, history)
    output = build_output(history, captured_at, errors, source_health)
    write_json(OUTPUT_PATH, output)
    coverage = output["coverage"]
    print(f"msc-action-intel fresh={len(fresh)} history={coverage['historical_tenders']} active={coverage['active_recent_tenders']} confirmed={coverage['tbmt_detail_confirmed']} investigate={coverage['investigate_now']} errors={len(errors)}")
    for error in errors[:20]: print(error)


if __name__ == "__main__":
    main()
