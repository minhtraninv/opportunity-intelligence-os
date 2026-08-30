#!/usr/bin/env python3
"""V1.4 Partner / Prime Radar from official MSC award-result metadata.

Purpose:
- keep OPEN notices in action_intel.py;
- use KQLCNT/result records only as historical market-relationship evidence;
- identify contractors that have actually won tracked categories before;
- connect those observed winners to current open tenders as partner candidates.

A historical winner is NOT evidence that the company is bidding the current package.
The output therefore calls them investigation candidates, never current bidders.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import action_intel as ai

ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = ROOT / "data" / "partner_history.json"
OUTPUT_PATH = ROOT / "data" / "partner_intelligence.json"
ACTION_PATH = ROOT / "data" / "action_intelligence.json"

KQLCNT_URL = ai.BASE + "/o/egp-portal-contractor-selection-v2/services/expose/contractor-input-result/get?token=fake"
SEARCH_PAGE_SIZE = 12
MAX_RESULT_DETAILS = 30
HISTORY_LIMIT = 3000
PARTNER_LIMIT = 80
MATCH_LIMIT = 5

OFFER_MAP = {
    "digital_services": [
        "OCR/scan/QC dữ liệu hoặc migration một phần",
        "Triển khai module, tích hợp hoặc hỗ trợ vận hành",
        "Nhân sự kỹ thuật theo sprint ngắn cho prime contractor",
    ],
    "office_goods": [
        "Sourcing đúng SKU/cấu hình theo HSMT",
        "Lắp đặt, cấu hình, giao nhận theo địa bàn",
        "Ghép distributor có hàng sẵn thay vì ôm tồn kho",
    ],
    "printing_media": [
        "Thiết kế/prepress/in một hạng mục tách được",
        "Kết nối xưởng có công suất và chia phần giao hàng",
        "Nhận QC, đóng gói hoặc giao nhận theo đơn",
    ],
    "maintenance": [
        "Nhận tuyến bảo trì/facility theo địa bàn",
        "Sourcing vật tư thay thế và nhân công kỹ thuật",
        "Làm subcontract cho phần việc định kỳ có SOP rõ",
    ],
    "garment_ppe": [
        "Sourcing xưởng may/PPE đúng tiêu chuẩn",
        "Nhận mẫu, size-set, đóng gói hoặc giao hàng",
        "Ghép năng lực sản xuất mà không ôm tồn kho trước",
    ],
    "food_services": [
        "Cung ứng một nhóm nguyên liệu hoặc tuyến giao",
        "Ghép bếp/xưởng đủ điều kiện vệ sinh an toàn",
        "Nhận logistics lạnh/định tuyến nếu tách được",
    ],
    "logistics": [
        "Nhận một tuyến/địa bàn thay vì toàn hợp đồng",
        "Ghép nhà xe/kho có năng lực sẵn",
        "Điều phối giao nhận và proof-of-delivery",
    ],
    "consulting": [
        "Ghép chuyên gia có hồ sơ năng lực phù hợp",
        "Nhận khảo sát, thu thập dữ liệu hoặc hồ sơ phụ trợ",
        "Hỗ trợ PMO/tài liệu cho đơn vị tư vấn chính",
    ],
    "medical": [
        "Chỉ tiếp cận qua distributor/đơn vị đủ pháp lý",
        "Nhận logistics, lắp đặt hoặc dịch vụ phụ trợ nếu được phép",
        "Không nhập hàng trước khi xác minh điều kiện và đơn chắc chắn",
    ],
    "machinery": [
        "Sourcing đại lý/nhà sản xuất đúng cấu hình",
        "Tìm phần lắp đặt, bảo trì hoặc đào tạo vận hành",
        "Không dùng vốn cá nhân để ôm thiết bị lớn",
    ],
    "construction": [
        "Tìm hạng mục thầu phụ nhỏ có thể bóc tách",
        "Cung ứng dịch vụ/vật tư phụ trợ theo đơn",
        "Không coi tổng thầu là đường vốn nhỏ",
    ],
    "other": [
        "Đọc HSMT để tìm phần việc có thể tách",
        "Ưu tiên sourcing/lead generation trước khi bỏ vốn",
        "Chỉ test sau khi xác định được người mua hoặc prime contractor",
    ],
}


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def result_search_payload(keyword: str):
    return [{
        "pageSize": SEARCH_PAGE_SIZE,
        "pageNumber": 0,
        "query": [{
            "index": "es-contractor-selection",
            "keyWord": keyword,
            "matchType": "exact",
            "matchFields": ["notifyNo", "bidName"],
            "filters": [{"fieldName": "type", "searchType": "in", "fieldValues": ["es-notify-contractor"]}],
        }],
    }]


def is_result_record(obj: dict) -> bool:
    step = ai.norm(ai.first_value(obj, "stepCode", "step")).lower()
    input_result_id = ai.norm(ai.first_value(obj, "inputResultId"))
    return bool(input_result_id) and ("kqlcnt" in step or "step-4" in step)


def search_result_records(keyword: str):
    root = ai.post_json(ai.SEARCH_URL, result_search_payload(keyword))
    rows, seen = [], set()
    for obj in ai.walk_objects(root):
        if not isinstance(obj, dict) or not is_result_record(obj):
            continue
        notify_no = ai.norm(ai.first_value(obj, "notifyNo"))
        input_result_id = ai.norm(ai.first_value(obj, "inputResultId"))
        title = ai.norm(ai.first_value(obj, "bidName"))
        if not notify_no or not input_result_id or not title:
            continue
        key = (notify_no, input_result_id)
        if key in seen:
            continue
        seen.add(key)
        copy = dict(obj)
        copy["_search_keyword"] = keyword
        rows.append(copy)
    return rows[:SEARCH_PAGE_SIZE]


def fetch_result(input_result_id: str):
    root = ai.post_json(KQLCNT_URL, {"id": input_result_id})
    if not isinstance(root, dict):
        return None
    main = root.get("bideContractorInputResultDTO")
    if isinstance(main, list):
        main = next((x for x in main if isinstance(x, dict)), None)
    if not isinstance(main, dict):
        main = ai.find_dict_with_field(root, "lotResultDTO")
    return main if isinstance(main, dict) else None


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def is_winner(contractor: dict) -> bool:
    value = ai.first_value(contractor, "bidResult", "result", "winner")
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(value) == 1
    return ai.norm(value).lower() in {"1", "true", "win", "winner", "trúng thầu", "trung thau"}


def stable_event_id(tender_code: str, contractor_code: str, contractor_name: str) -> str:
    raw = f"{tender_code}|{contractor_code}|{contractor_name}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:20]


def winner_events(search_obj: dict, main: dict, captured_at: datetime):
    tender_code = ai.norm(ai.first_value(main, "notifyNo") or ai.first_value(search_obj, "notifyNo"))
    title = ai.norm(ai.first_value(main, "bidName") or ai.first_value(search_obj, "bidName"))
    buyer = ai.norm(ai.first_value(main, "investorName", "procuringEntityName") or ai.first_value(search_obj, "investorName", "procuringEntityName") or "Chưa xác định")
    published = ai.parse_datetime(ai.first_value(main, "publicDate", "publishDate") or ai.first_value(search_obj, "publicDate", "publishDate", "createdDate"))
    category = ai.classify(title)
    keyword = search_obj.get("_search_keyword")
    events = []

    lots = as_list(main.get("lotResultDTO"))
    for lot in lots:
        if not isinstance(lot, dict):
            continue
        contractors = as_list(lot.get("contractorList"))
        winning_code = ai.norm(ai.first_value(lot, "winningCode", "winnerCode"))
        for contractor in contractors:
            if not isinstance(contractor, dict):
                continue
            contractor_code = ai.norm(ai.first_value(contractor, "orgCode", "contractorCode", "taxCode"))
            contractor_name = ai.norm(ai.first_value(contractor, "orgFullname", "contractorName", "orgName"))
            winner_by_code = bool(winning_code and contractor_code and winning_code == contractor_code)
            if not (is_winner(contractor) or winner_by_code):
                continue
            if not contractor_name:
                continue
            price = ai.number_value(ai.first_value(contractor, "bidWiningPrice", "winningPrice", "lotFinalPrice"))
            event_id = stable_event_id(tender_code, contractor_code, contractor_name)
            events.append({
                "id": event_id,
                "record_type": "award_winner_observation",
                "tender_code": tender_code,
                "tender_title": title,
                "buyer": buyer,
                "procurement_category": category,
                "matched_keyword": keyword,
                "input_result_id": ai.norm(ai.first_value(search_obj, "inputResultId")),
                "contractor_name": contractor_name,
                "contractor_code": contractor_code or None,
                "tax_code": ai.norm(ai.first_value(contractor, "taxCode")) or None,
                "winning_price_vnd": price,
                "award_public_at": ai.iso(published) if published else None,
                "source_name": "Hệ thống mạng đấu thầu quốc gia",
                "source_url": ai.detail_url(search_obj),
                "authority": 1.0,
                "evidence_type": "official_award_result",
                "first_seen_at": ai.iso(captured_at),
                "last_seen_at": ai.iso(captured_at),
            })
    return events


def collect(captured_at: datetime):
    raw, errors, health = [], [], []
    for keyword in ai.SEARCH_KEYWORDS:
        try:
            rows = search_result_records(keyword)
            health.append({"keyword": keyword, "result_records": len(rows), "status": "ok", "error": None})
            raw.extend(rows)
        except Exception as exc:
            message = f"MSC KQLCNT search '{keyword}': {type(exc).__name__}: {exc}"
            errors.append(message)
            health.append({"keyword": keyword, "result_records": 0, "status": "error", "error": message})

    dedup = {}
    for row in raw:
        key = ai.norm(ai.first_value(row, "inputResultId"))
        if not key:
            continue
        if key in dedup:
            previous = dedup[key]
            kws = set(previous.get("_matched_keywords", [previous.get("_search_keyword")]))
            kws.add(row.get("_search_keyword"))
            previous["_matched_keywords"] = sorted(x for x in kws if x)
        else:
            row["_matched_keywords"] = [row.get("_search_keyword")]
            dedup[key] = row

    rows = list(dedup.values())
    rows.sort(key=lambda x: ai.parse_datetime(ai.first_value(x, "publicDate", "publishDate", "createdDate")) or datetime(1970, 1, 1, tzinfo=timezone.utc), reverse=True)

    events = []
    for row in rows[:MAX_RESULT_DETAILS]:
        input_result_id = ai.norm(ai.first_value(row, "inputResultId"))
        try:
            main = fetch_result(input_result_id)
            if not main:
                continue
            new_events = winner_events(row, main, captured_at)
            for event in new_events:
                if row.get("_matched_keywords"):
                    event["matched_keywords"] = row["_matched_keywords"]
            events.extend(new_events)
        except Exception as exc:
            errors.append(f"KQLCNT {input_result_id}: {type(exc).__name__}: {exc}")
    return events, errors, health, len(rows[:MAX_RESULT_DETAILS])


def merge_history(old: dict, fresh: list[dict], captured_at: datetime):
    by_id = {x["id"]: dict(x) for x in old.get("items", []) if x.get("id")}
    for item in fresh:
        previous = by_id.get(item["id"])
        if previous:
            keywords = sorted(set(previous.get("matched_keywords", []) + item.get("matched_keywords", [])))
            by_id[item["id"]] = {
                **previous,
                **item,
                "matched_keywords": keywords,
                "first_seen_at": previous.get("first_seen_at") or item["first_seen_at"],
                "last_seen_at": ai.iso(captured_at),
            }
        else:
            by_id[item["id"]] = item
    items = list(by_id.values())
    items.sort(key=lambda x: x.get("award_public_at") or x.get("first_seen_at") or "", reverse=True)
    return {"version": 1, "updated_at": ai.iso(captured_at), "items": items[:HISTORY_LIMIT]}


def partner_key(event: dict):
    return event.get("contractor_code") or ai.norm(event.get("contractor_name")).casefold()


def aggregate_partners(history: dict, captured_at: datetime):
    grouped = defaultdict(list)
    for event in history.get("items", []):
        key = partner_key(event)
        if key:
            grouped[key].append(event)

    partners = []
    for key, events in grouped.items():
        events.sort(key=lambda x: x.get("award_public_at") or x.get("first_seen_at") or "", reverse=True)
        latest = events[0]
        categories = Counter(x.get("procurement_category", "other") for x in events)
        buyers = Counter(x.get("buyer", "Chưa xác định") for x in events)
        prices = [x.get("winning_price_vnd") for x in events if isinstance(x.get("winning_price_vnd"), (int, float))]
        latest_dt = ai.parse_datetime(latest.get("award_public_at"))
        recency_bonus = 10 if latest_dt and captured_at - latest_dt <= timedelta(days=90) else 4
        score = min(95, 48 + min(28, len(events) * 7) + recency_bonus + min(9, len(categories) * 3))
        partners.append({
            "partner_id": key,
            "contractor_name": latest.get("contractor_name"),
            "contractor_code": latest.get("contractor_code"),
            "tax_code": latest.get("tax_code"),
            "observed_wins": len(events),
            "observed_winning_value_vnd": sum(prices) if prices else None,
            "categories": [name for name, _ in categories.most_common()],
            "category_counts": dict(categories),
            "buyers_observed": [name for name, _ in buyers.most_common(5)],
            "latest_win_at": latest.get("award_public_at"),
            "latest_tender_code": latest.get("tender_code"),
            "latest_tender_title": latest.get("tender_title"),
            "latest_source_url": latest.get("source_url"),
            "partner_evidence_score": score,
            "evidence_status": "historical_official_winner_observed",
            "caveat": "Đã thắng gói tương tự trong mẫu theo dõi; không có nghĩa đang dự thầu gói hiện tại.",
            "examples": [{
                "tender_code": x.get("tender_code"),
                "title": x.get("tender_title"),
                "buyer": x.get("buyer"),
                "winning_price_vnd": x.get("winning_price_vnd"),
                "award_public_at": x.get("award_public_at"),
                "source_url": x.get("source_url"),
            } for x in events[:3]],
        })
    partners.sort(key=lambda x: (x.get("partner_evidence_score", 0), x.get("latest_win_at") or ""), reverse=True)
    return partners[:PARTNER_LIMIT]


def match_score(trigger: dict, partner: dict):
    category = trigger.get("procurement_category", "other")
    count = int(partner.get("category_counts", {}).get(category, 0))
    if count <= 0:
        return 0
    score = 48 + min(25, count * 8)
    if trigger.get("buyer") in partner.get("buyers_observed", []):
        score += 12
    latest = ai.parse_datetime(partner.get("latest_win_at"))
    if latest and datetime.now(timezone.utc) - latest <= timedelta(days=180):
        score += 8
    return min(95, score)


def execution_brief(trigger: dict, candidates: list[dict]):
    category = trigger.get("procurement_category", "other")
    path = trigger.get("recommended_path", "watch_only")
    names = [x.get("contractor_name") for x in candidates[:3] if x.get("contractor_name")]
    if path == "potential_prime_or_partner":
        route = "Xác minh HSMT trước; nếu đủ năng lực thật mới cân nhắc prime/partner. Không lấy điểm prior làm bằng chứng đủ điều kiện."
    elif path == "subcontract_or_sourcing":
        route = "Ưu tiên bán phần việc/sourcing cho prime contractor; không đứng tổng gói nếu working capital và năng lực không phù hợp."
    else:
        route = "Chỉ theo dõi cho đến khi tìm được phần việc tách được và người mua/prime contractor rõ ràng."
    target = (
        f"Điều tra trước các historical winners: {', '.join(names)}."
        if names else
        "Chưa có historical winner đủ bằng chứng trong mẫu; tìm prime contractor từ KQLCNT các gói cùng loại trước khi chào bán."
    )
    return {
        "tender_code": trigger.get("tender_code"),
        "buyer": trigger.get("buyer"),
        "title": trigger.get("title"),
        "category": category,
        "recommended_path": path,
        "route": route,
        "target_counterpart": target,
        "offers_to_test": OFFER_MAP.get(category, OFFER_MAP["other"]),
        "test_budget_vnd": 2_000_000,
        "actions_48h": [
            f"Mở {trigger.get('tender_code')} và bóc 5 điểm: phạm vi, bảo lãnh, hợp đồng tương tự, nhân sự/pháp lý, lịch thanh toán.",
            "Đánh dấu phần việc có thể tách khỏi prime contract mà không cần ôm hàng/vốn lớn.",
            "Chọn tối đa 3 historical winner candidates có cùng category; kiểm tra website/kênh chính thức và năng lực hiện tại.",
            "Gửi một đề xuất rất ngắn: phần việc cụ thể + năng lực cung cấp + giá/đơn vị sơ bộ + thời gian đáp ứng.",
            "Không mua hàng, tuyển người hay chi quảng cáo lớn trước khi có phản hồi thương mại thật.",
        ],
        "success_signal": "Ít nhất 1 đối tác đủ năng lực xác nhận đang quan tâm loại công việc này và yêu cầu hồ sơ/báo giá/trao đổi phạm vi cụ thể.",
        "kill_signal": "Không có phần việc tách được, yêu cầu HSMT khóa hoàn toàn vào năng lực prime, hoặc 5 đối tác phù hợp đều không thấy nhu cầu thực tế.",
        "evidence_gap": "Chưa biết ai đang dự thầu gói hiện tại; historical winner chỉ là danh sách điều tra ưu tiên.",
    }


def build_matches(action_data: dict, partners: list[dict]):
    matches, briefs = [], []
    triggers = action_data.get("buyer_triggers", []) if isinstance(action_data, dict) else []
    for trigger in triggers:
        ranked = []
        for partner in partners:
            score = match_score(trigger, partner)
            if score <= 0:
                continue
            ranked.append({
                "partner_id": partner.get("partner_id"),
                "contractor_name": partner.get("contractor_name"),
                "contractor_code": partner.get("contractor_code"),
                "match_score": score,
                "observed_wins_same_category": partner.get("category_counts", {}).get(trigger.get("procurement_category", "other"), 0),
                "latest_win_at": partner.get("latest_win_at"),
                "latest_tender_title": partner.get("latest_tender_title"),
                "latest_source_url": partner.get("latest_source_url"),
                "caveat": partner.get("caveat"),
            })
        ranked.sort(key=lambda x: (x.get("match_score", 0), x.get("latest_win_at") or ""), reverse=True)
        ranked = ranked[:MATCH_LIMIT]
        matches.append({
            "tender_code": trigger.get("tender_code"),
            "category": trigger.get("procurement_category"),
            "recommended_path": trigger.get("recommended_path"),
            "candidates": ranked,
        })
        briefs.append(execution_brief(trigger, ranked))
    return matches, briefs


def build_output(history: dict, captured_at: datetime, errors: list[str], health: list[dict], details_fetched: int):
    partners = aggregate_partners(history, captured_at)
    action_data = load_json(ACTION_PATH, {})
    matches, briefs = build_matches(action_data, partners)
    matched_open = sum(bool(x.get("candidates")) for x in matches)
    return {
        "meta": {
            "version": "1.4.0",
            "generated_at": ai.iso(captured_at),
            "mode": "official_award_history_partner_radar",
            "principle": "historical_winner_is_candidate_not_current_bidder",
        },
        "coverage": {
            "historical_winner_events": len(history.get("items", [])),
            "result_details_fetched_last_run": details_fetched,
            "unique_partner_candidates": len(partners),
            "open_tenders_with_partner_candidates": matched_open,
            "source_errors_last_run": len(errors),
        },
        "source_health": health,
        "partner_candidates": partners,
        "matches_by_open_tender": matches,
        "execution_briefs": briefs,
        "warnings": [
            "Historical winner = đã thắng trong mẫu KQLCNT theo dõi; KHÔNG phải bằng chứng doanh nghiệp đang tham gia gói hiện tại.",
            "Danh sách này ưu tiên điều tra đối tác/prime contractor, không phải khuyến nghị liên hệ mù quáng hay bỏ vốn.",
            "Phải xác minh website/kênh chính thức, năng lực hiện tại và phạm vi HSMT trước khi đề xuất hợp tác.",
            *([f"Có {len(errors)} lỗi request/schema ở lần chạy gần nhất; không suy diễn từ dữ liệu thiếu."] if errors else []),
        ],
    }


def main():
    captured = ai.now_utc()
    fresh, errors, health, details_fetched = collect(captured)
    history = merge_history(load_json(HISTORY_PATH, {"version": 1, "items": []}), fresh, captured)
    write_json(HISTORY_PATH, history)
    output = build_output(history, captured, errors, health, details_fetched)
    write_json(OUTPUT_PATH, output)
    c = output["coverage"]
    print(
        "partner-radar "
        f"fresh_winners={len(fresh)} history={c['historical_winner_events']} "
        f"partners={c['unique_partner_candidates']} matched_open={c['open_tenders_with_partner_candidates']} "
        f"errors={c['source_errors_last_run']}"
    )
    for error in errors[:20]:
        print(error)


if __name__ == "__main__":
    main()
