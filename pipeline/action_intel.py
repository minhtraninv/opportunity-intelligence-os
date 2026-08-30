#!/usr/bin/env python3
"""V1.3 Procurement Action Intelligence using Mua Sam Cong website endpoints.

Only OPEN tender notices enter Buyer Radar. Award/result records are deliberately kept
out of this pipeline (they will later become a separate prime-contractor radar).
Small-capital scores distinguish PRIME fit from SUBCONTRACT/SOURCING fit; neither is a
claim of eligibility until HSMT requirements are checked.
"""
from __future__ import annotations

import json
import re
import ssl
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
ACTIVE_LIMIT = 60
SEARCH_PAGE_SIZE = 8
MAX_DETAIL_REQUESTS = 24

SEARCH_KEYWORDS = (
    "vệ sinh", "bảo trì", "in ấn", "văn phòng phẩm", "đồng phục", "phần mềm",
    "số hóa", "thuê xe", "suất ăn", "bảo hộ lao động", "máy tính", "tư vấn",
)

# Specific goods phrases run before generic IT phrases so “máy tính, thiết bị CNTT”
# is not incorrectly scored like a software-services package.
CATEGORY_RULES = (
    ("office_goods", ("văn phòng phẩm", "máy tính", "máy in", "mực in", "thiết bị văn phòng", "bàn ghế")),
    ("digital_services", ("phần mềm", "website", "hệ thống thông tin", "chuyển đổi số", "số hóa", "gis", "dịch vụ công nghệ thông tin")),
    ("printing_media", ("in ấn", "in tài liệu", "in báo", "ấn phẩm", "thiết kế", "truyền thông")),
    ("consulting", ("tư vấn", "khảo sát", "giám sát", "thẩm tra", "lập hồ sơ")),
    ("maintenance", ("bảo trì", "bảo dưỡng", "sửa chữa", "vệ sinh", "kiểm định")),
    ("garment_ppe", ("đồng phục", "bảo hộ lao động", "ppe", "quần áo bảo hộ", "giày bảo hộ")),
    ("food_services", ("suất ăn", "thực phẩm", "catering", "nước uống", "bếp ăn")),
    ("logistics", ("thuê xe", "vận chuyển", "vận tải", "logistics", "giao nhận", "kho bãi")),
    ("medical", ("thuốc", "vật tư y tế", "thiết bị y tế", "xét nghiệm", "dược")),
    ("machinery", ("máy móc", "phụ tùng", "thiết bị công nghiệp")),
    ("construction", ("thi công", "xây dựng", "xây lắp", "công trình")),
)

SUBCONTRACT_PRIOR = {
    "digital_services": 88, "printing_media": 85, "consulting": 78, "maintenance": 80,
    "office_goods": 74, "garment_ppe": 72, "food_services": 65, "logistics": 64,
    "medical": 38, "machinery": 38, "construction": 45, "other": 48,
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
    "machinery": ["Sourcing/giới thiệu đại lý", "Tìm phần lắp đặt/bảo trì", "Tránh ôm thiết bị bằng vốn cá nhân"],
    "construction": ["Tìm hạng mục thầu phụ nhỏ", "Cung ứng dịch vụ/vật tư phụ trợ", "Không coi tổng thầu là cơ hội vốn nhỏ"],
    "other": ["Đọc phạm vi rồi tìm hạng mục nhỏ", "Ưu tiên sourcing/lead generation", "Chỉ bỏ vốn sau khi buyer và điều kiện rõ"],
}


class LegacyDhAdapter(HTTPAdapter):
    """Support MSC legacy DH without disabling CA or hostname verification."""
    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        context = ssl.create_default_context()
        context.set_ciphers("DEFAULT:@SECLEVEL=1")
        pool_kwargs["ssl_context"] = context
        return super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)


def build_session() -> requests.Session:
    retry = Retry(
        total=2, connect=2, read=2, status=2, backoff_factor=0.7,
        status_forcelist=(408, 429, 500, 502, 503, 504),
        allowed_methods=frozenset({"POST"}), raise_on_status=False,
    )
    session = requests.Session()
    session.mount("https://muasamcong.mpi.gov.vn/", LegacyDhAdapter(max_retries=retry))
    session.headers.update({
        "User-Agent": "Mozilla/5.0", "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json; charset=utf-8", "Origin": BASE,
        "Referer": OFFICIAL_HOME, "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.7",
    })
    return session


SESSION = build_session()


def now_utc() -> datetime: return datetime.now(timezone.utc)
def iso(dt: datetime) -> str: return dt.astimezone(timezone.utc).isoformat()
def norm(value) -> str: return re.sub(r"\s+", " ", str(value or "")).strip()


def load_json(path: Path, default):
    if not path.exists(): return default
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return default


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def post_json(url: str, payload, timeout: int = 25):
    response = SESSION.post(url, json=payload, timeout=(10, timeout))
    response.raise_for_status()
    if "json" not in response.headers.get("content-type", "").lower() and not response.text.lstrip().startswith(("{", "[")):
        raise ValueError("non-JSON response")
    return response.json()


def walk_objects(node):
    if isinstance(node, dict):
        yield node
        for value in node.values(): yield from walk_objects(value)
    elif isinstance(node, list):
        for value in node: yield from walk_objects(value)


def scalar(value):
    if isinstance(value, list):
        for item in value:
            result = scalar(item)
            if result not in (None, ""): return result
        return None
    return value


def first_value(obj: dict | None, *names):
    if not isinstance(obj, dict): return None
    for name in names:
        value = scalar(obj.get(name))
        if value is None: continue
        if isinstance(value, str):
            value = value.strip()
            if not value or value.lower() in {"undefined", "null"}: continue
        return value
    return None


def find_dict_with_field(node, field: str):
    for obj in walk_objects(node):
        if obj.get(field) is not None: return obj
    return None


def parse_datetime(value) -> datetime | None:
    value = scalar(value)
    if value is None: return None
    if isinstance(value, (int, float)):
        stamp = float(value) / (1000 if float(value) > 10_000_000_000 else 1)
        try: return datetime.fromtimestamp(stamp, tz=timezone.utc)
        except Exception: return None
    text = norm(value)
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None: dt = dt.replace(tzinfo=VN_TZ)
            return dt.astimezone(timezone.utc)
        except ValueError: pass
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
        try: return datetime.strptime(text, fmt).replace(tzinfo=VN_TZ).astimezone(timezone.utc)
        except ValueError: pass
    return None


def number_value(value):
    value = scalar(value)
    if value is None or isinstance(value, bool): return None
    if isinstance(value, (int, float)): return value
    try: return float(norm(value).replace(",", ""))
    except ValueError: return None


def classify(title: str) -> str:
    lowered = norm(title).casefold()
    for category, phrases in CATEGORY_RULES:
        if any(phrase.casefold() in lowered for phrase in phrases): return category
    return "other"


def search_payload(keyword: str) -> list[dict]:
    return [{"pageSize": SEARCH_PAGE_SIZE, "pageNumber": 0, "query": [{
        "index": "es-contractor-selection", "keyWord": keyword, "matchType": "exact",
        "matchFields": ["notifyNo", "bidName"],
        "filters": [{"fieldName": "type", "searchType": "in", "fieldValues": ["es-notify-contractor"]}],
    }]}]


def is_open_notice(obj: dict, captured_at: datetime) -> bool:
    step = norm(first_value(obj, "stepCode", "step")).lower()
    if "kqlcnt" in step or "step-4" in step: return False
    closes = parse_datetime(first_value(obj, "bidCloseDate"))
    if closes and closes <= captured_at + timedelta(hours=1): return False
    return "step-1" in step or bool(closes)


def search_keyword(keyword: str, captured_at: datetime) -> tuple[list[dict], str | None]:
    try: root = post_json(SEARCH_URL, search_payload(keyword))
    except Exception as exc: return [], f"MSC search '{keyword}': {type(exc).__name__}: {exc}"
    matches, seen = [], set()
    for obj in walk_objects(root):
        notify_no = norm(first_value(obj, "notifyNo"))
        notify_id = norm(first_value(obj, "notifyId", "id"))
        title = norm(first_value(obj, "bidName"))
        if not notify_no or not notify_id or not title or notify_no in seen: continue
        if not is_open_notice(obj, captured_at): continue
        seen.add(notify_no)
        matches.append({**obj, "_search_keyword": keyword})
    return matches[:SEARCH_PAGE_SIZE], None


def fetch_tbmt(notify_id: str):
    try:
        root = post_json(TBMT_URL, {"id": notify_id})
        main = root.get("bidoNotifyContractorM") if isinstance(root, dict) else None
        main = scalar(main)
        if not isinstance(main, dict): main = find_dict_with_field(root, "bidName")
        return main, None
    except Exception as exc: return None, f"TBMT {notify_id}: {type(exc).__name__}: {exc}"


def detail_url(search_obj: dict) -> str:
    params = {
        "p_p_id": "egpportalcontractorselectionv2_WAR_egpportalcontractorselectionv2", "p_p_lifecycle": "0",
        "p_p_state": "normal", "p_p_mode": "view",
        "_egpportalcontractorselectionv2_WAR_egpportalcontractorselectionv2_render": "detail-v2",
        "type": "es-notify-contractor", "stepCode": first_value(search_obj, "stepCode", "step") or "undefined",
        "id": first_value(search_obj, "id", "notifyId") or "undefined", "notifyId": first_value(search_obj, "notifyId", "id") or "undefined",
        "inputResultId": first_value(search_obj, "inputResultId") or "undefined", "bidOpenId": first_value(search_obj, "bidOpenId") or "undefined",
        "processApply": first_value(search_obj, "processApply") or "LDT", "bidMode": first_value(search_obj, "bidMode") or "undefined",
        "notifyNo": first_value(search_obj, "notifyNo") or "undefined", "planNo": first_value(search_obj, "planNo") or "undefined",
        "step": "tbmt", "isInternet": first_value(search_obj, "isInternet") or "undefined", "bidForm": first_value(search_obj, "bidForm") or "undefined",
    }
    return BASE + "/web/guest/contractor-selection?" + urlencode(params)


def normalize_tender(search_obj: dict, detail: dict | None, captured_at: datetime) -> dict:
    notify_no = norm(first_value(search_obj, "notifyNo") or first_value(detail, "notifyNo"))
    title = norm(first_value(detail, "bidName") or first_value(search_obj, "bidName"))
    buyer = norm(first_value(detail, "investorName", "procuringEntityName") or first_value(search_obj, "investorName", "procuringEntityName") or "Chưa xác định")
    posted = parse_datetime(first_value(search_obj, "publicDate", "publishDate", "createdDate") or first_value(detail, "publicDate", "publishDate", "createdDate"))
    closes = parse_datetime(first_value(detail, "bidCloseDate") or first_value(search_obj, "bidCloseDate"))
    opens = parse_datetime(first_value(detail, "bidOpenDate") or first_value(search_obj, "bidOpenDate"))
    price = number_value(first_value(detail, "bidEstimatePrice", "bidPrice") or first_value(search_obj, "bidPrice", "bidEstimatePrice"))
    return {
        "id": notify_no, "record_type": "open_notice", "tender_code": notify_no,
        "notify_id": norm(first_value(search_obj, "notifyId", "id") or first_value(detail, "id", "notifyId")),
        "title": title, "buyer": buyer, "posted_at": iso(posted) if posted else None,
        "closes_at": iso(closes) if closes else None, "opens_at": iso(opens) if opens else None,
        "days_to_close": round((closes - captured_at).total_seconds() / 86400, 1) if closes else None,
        "package_price_vnd": price, "procurement_category": classify(title),
        "matched_keywords": [search_obj.get("_search_keyword")], "source_id": "msc-official",
        "source_name": "Hệ thống mạng đấu thầu quốc gia", "source_url": detail_url(search_obj),
        "authority": 1.0, "official_metadata": True, "tbmt_detail_confirmed": bool(detail),
        "requirements_status": "unverified", "first_seen_at": iso(captured_at), "last_seen_at": iso(captured_at),
    }


def collect(captured_at: datetime) -> tuple[list[dict], list[str], list[dict]]:
    raw_matches, errors, health = [], [], []
    for keyword in SEARCH_KEYWORDS:
        matches, error = search_keyword(keyword, captured_at)
        raw_matches.extend(matches)
        health.append({"keyword": keyword, "open_results": len(matches), "status": "error" if error else "ok", "error": error})
        if error: errors.append(error)

    by_notify = {}
    for obj in raw_matches:
        code = norm(first_value(obj, "notifyNo"))
        if not code: continue
        if code in by_notify:
            kws = set(by_notify[code].get("_matched_keywords", [by_notify[code].get("_search_keyword")]))
            kws.add(obj.get("_search_keyword")); by_notify[code]["_matched_keywords"] = sorted(x for x in kws if x)
        else:
            obj["_matched_keywords"] = [obj.get("_search_keyword")]; by_notify[code] = obj

    candidates = list(by_notify.values())
    candidates.sort(key=lambda x: parse_datetime(first_value(x, "publicDate", "publishDate", "createdDate")) or datetime(1970,1,1,tzinfo=timezone.utc), reverse=True)
    rows, budget = [], MAX_DETAIL_REQUESTS
    for search_obj in candidates:
        detail, error = None, None
        notify_id = norm(first_value(search_obj, "notifyId", "id"))
        if notify_id and budget > 0:
            detail, error = fetch_tbmt(notify_id); budget -= 1
            if error: errors.append(error)
        row = normalize_tender(search_obj, detail, captured_at)
        row["matched_keywords"] = search_obj.get("_matched_keywords", [search_obj.get("_search_keyword")])
        rows.append(row)
    return rows, errors, health


def is_real_tender_history(item: dict) -> bool:
    if item.get("record_type") == "open_notice": return True
    posted, closes = parse_datetime(item.get("posted_at")), parse_datetime(item.get("closes_at"))
    return bool(posted and closes and (closes - posted).total_seconds() > 3600)


def merge_history(old: dict, fresh: list[dict], captured_at: datetime) -> dict:
    by_id = {item["id"]: dict(item) for item in old.get("items", []) if item.get("id") and is_real_tender_history(item)}
    for item in fresh:
        previous = by_id.get(item["id"])
        if previous:
            keywords = sorted(set(previous.get("matched_keywords", []) + item.get("matched_keywords", [])))
            by_id[item["id"]] = {**previous, **item, "matched_keywords": keywords, "first_seen_at": previous.get("first_seen_at") or item["first_seen_at"], "last_seen_at": iso(captured_at)}
        else: by_id[item["id"]] = item
    items = list(by_id.values()); items.sort(key=lambda x: x.get("posted_at") or x.get("first_seen_at") or "", reverse=True)
    return {"version": 3, "updated_at": iso(captured_at), "items": items[:HISTORY_LIMIT]}


def price_band(price):
    if price is None: return "unknown"
    if price <= 100_000_000: return "small"
    if price <= 500_000_000: return "medium"
    if price <= 2_000_000_000: return "large"
    return "very_large"


def capital_paths(category: str, price):
    sub = SUBCONTRACT_PRIOR.get(category, 48)
    if price is None:
        prime = None
    else:
        prime = sub
        if price > 2_000_000_000: prime -= 55
        elif price > 500_000_000: prime -= 35
        elif price > 100_000_000: prime -= 15
        if category in {"medical", "machinery", "construction"}: prime -= 15
        prime = max(5, min(95, prime))
    if prime is not None and prime >= 65: path = "potential_prime_or_partner"
    elif sub >= 60: path = "subcontract_or_sourcing"
    else: path = "watch_only"
    return prime, sub, path


def score_trigger(item: dict, captured_at: datetime) -> dict:
    category = item.get("procurement_category", "other")
    prime_fit, sub_fit, path = capital_paths(category, item.get("package_price_vnd"))
    path_fit = prime_fit if path == "potential_prime_or_partner" else sub_fit
    score = 30 + 12 + (8 if item.get("tbmt_detail_confirmed") else 0)
    if item.get("buyer") and item.get("buyer") != "Chưa xác định": score += 8
    if item.get("package_price_vnd") is not None: score += 4
    closes = parse_datetime(item.get("closes_at")); days = round((closes-captured_at).total_seconds()/86400,1) if closes else None
    if days is not None:
        if 4 <= days <= 21: score += 10
        elif 2 <= days < 4: score += 4
        elif days < 0: score -= 35
    posted = parse_datetime(item.get("posted_at"))
    if posted and (captured_at-posted).total_seconds() <= 3*86400: score += 5
    score += round(path_fit * 0.12)
    score = max(0, min(95, score))
    if days is not None and days < 0: action = "closed"
    elif days is not None and days < 2: action = "too_late"
    elif score >= 82: action = "investigate_now"
    elif score >= 64: action = "watch"
    else: action = "context"
    return {
        **item, "days_to_close": days, "package_price_band": price_band(item.get("package_price_vnd")),
        "prime_fit_score": prime_fit, "subcontract_fit_score": sub_fit, "recommended_path": path,
        "small_capital_fit_score": path_fit, "small_capital_fit_status": "requirements_unverified",
        "buyer_trigger_score": score, "action_level": action, "small_capital_angles": ANGLES.get(category, ANGLES["other"]),
        "verification_required": True, "official_verification_url": item.get("source_url") or OFFICIAL_HOME,
        "next_action": f"Mở mã {item.get('tender_code')} trên Hệ thống mạng đấu thầu quốc gia. Đọc HSMT: bảo đảm dự thầu, doanh thu/hợp đồng tương tự, nhân sự, giấy phép và điều khoản thanh toán. Nếu prime contract vượt khả năng, tìm nhà thầu phù hợp để đề xuất sourcing/thầu phụ thay vì tự ôm vốn.",
        "kill_criteria": "Loại nếu thời hạn quá sát, yêu cầu pháp lý/doanh thu/bảo lãnh vượt khả năng, dòng tiền buộc phải vay/ôm hàng quá mức, hoặc không tìm được đường prime/partner/thầu phụ thực tế.",
    }


def build_output(history: dict, captured_at: datetime, errors: list[str], health: list[dict]) -> dict:
    scored = [score_trigger(item,captured_at) for item in history.get("items", [])]
    cutoff = captured_at - timedelta(days=45)
    active = [item for item in scored if item.get("action_level") not in {"closed","too_late"} and (not item.get("posted_at") or (parse_datetime(item.get("posted_at")) or cutoff) >= cutoff)]
    active.sort(key=lambda x:(x.get("buyer_trigger_score",0),x.get("posted_at") or ""), reverse=True)
    categories = Counter(item.get("procurement_category","other") for item in active)
    return {
        "meta": {"version":"1.3.3","generated_at":iso(captured_at),"mode":"official_msc_open_tender_intelligence","principle":"official_metadata_then_requirements_verification","api_stability":"website_endpoint_not_published_developer_api","tls_mode":"certificate_verified_legacy_dh_seclevel1"},
        "coverage": {"historical_open_tenders":len(history.get("items",[])),"active_recent_tenders":len(active),"tbmt_detail_confirmed":sum(bool(x.get("tbmt_detail_confirmed")) for x in active),"investigate_now":sum(x.get("action_level")=="investigate_now" for x in active),"watch":sum(x.get("action_level")=="watch" for x in active),"source_errors_last_run":len(errors)},
        "category_summary":dict(categories.most_common()),"source_health":health,"buyer_triggers":active[:ACTIVE_LIMIT],
        "warnings":[
            "Chỉ TBMT còn mở được đưa vào Buyer Radar; KQLCNT/step 4 đã tách khỏi pipeline này.",
            "Prime fit và subcontract fit là hai đường khác nhau. Gói lớn có thể tệ cho prime-bid nhưng vẫn đáng điều tra để bán cho nhà thầu chính.",
            "HSMT, bảo lãnh, doanh thu tương tự, pháp lý và điều khoản thanh toán vẫn phải xác minh trước khi bỏ tiền.",
            "Endpoint là endpoint website MSC, không phải developer API được cam kết ổn định.",
            *([f"Có {len(errors)} lỗi request/schema ở lần chạy gần nhất; không suy diễn từ dữ liệu thiếu."] if errors else []),
        ],
    }


def main() -> None:
    captured = now_utc(); fresh, errors, health = collect(captured)
    history = merge_history(load_json(HISTORY_PATH,{"version":3,"items":[]}),fresh,captured); write_json(HISTORY_PATH,history)
    output = build_output(history,captured,errors,health); write_json(OUTPUT_PATH,output)
    c=output["coverage"]
    print(f"msc-open-tenders fresh={len(fresh)} history={c['historical_open_tenders']} active={c['active_recent_tenders']} confirmed={c['tbmt_detail_confirmed']} investigate={c['investigate_now']} watch={c['watch']} errors={len(errors)}")
    for error in errors[:20]: print(error)


if __name__ == "__main__": main()
