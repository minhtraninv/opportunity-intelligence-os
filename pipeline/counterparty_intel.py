#!/usr/bin/env python3
"""V1.5 Counterparty Dossiers: turn buyer triggers + award history into outreach research targets.

This layer never invents emails, phone numbers, people, or current bidder status.
A counterparty is an investigation target supported by observed public award history.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ACTION_PATH = DATA / "action_intelligence.json"
PARTNER_PATH = DATA / "partner_intelligence.json"
RELATIONSHIP_PATH = DATA / "relationship_intelligence.json"
OUTPUT_PATH = DATA / "counterparty_intelligence.json"

ROLE_MAP = {
    "digital_services": ["Business Development / Sales B2G", "Project Manager / Delivery", "Technical Lead / Solution"],
    "office_goods": ["Sales dự án", "Procurement / Sourcing", "Kinh doanh kênh dự án"],
    "printing_media": ["Sales dự án", "Account / Production", "Điều phối sản xuất"],
    "maintenance": ["Kinh doanh dự án", "Service / Facility Manager", "Điều phối kỹ thuật"],
    "garment_ppe": ["Sales dự án", "Sourcing / Production", "Merchandising / Điều phối đơn hàng"],
    "food_services": ["Kinh doanh B2B/B2G", "Vận hành cung ứng", "Mua hàng / Supply"],
    "logistics": ["Sales B2B/B2G", "Operations", "Điều phối tuyến / Fleet"],
    "consulting": ["Business Development", "Project Director / PM", "Chuyên gia phụ trách hồ sơ"],
    "medical": ["Sales dự án / Tender", "Regulatory / Hồ sơ", "Service / Installation"],
    "machinery": ["Sales dự án", "Technical Sales", "Service / Installation"],
    "construction": ["Business Development / Đấu thầu", "Project Manager", "Procurement / Subcontract"],
    "other": ["Business Development", "Người phụ trách dự án", "Procurement / Operations"],
}

OFFER_MAP = {
    "digital_services": ["OCR/scan/QC hoặc migration một phần", "nhân sự triển khai/module ngách", "hỗ trợ vận hành sau triển khai"],
    "office_goods": ["sourcing đúng SKU/cấu hình", "giao nhận/lắp đặt theo địa bàn", "kết nối distributor có hàng sẵn"],
    "printing_media": ["thiết kế/prepress/in hạng mục tách được", "QC/đóng gói", "giao nhận theo đơn"],
    "maintenance": ["tuyến bảo trì theo địa bàn", "nhân công kỹ thuật", "sourcing vật tư thay thế"],
    "garment_ppe": ["sourcing xưởng/PPE đúng chuẩn", "mẫu-size set-đóng gói", "giao hàng theo địa bàn"],
    "food_services": ["cung ứng một nhóm nguyên liệu", "một tuyến giao", "logistics lạnh/phụ trợ"],
    "logistics": ["một tuyến/địa bàn", "ghép nhà xe/kho", "điều phối và proof-of-delivery"],
    "consulting": ["khảo sát/thu thập dữ liệu", "PMO/tài liệu", "ghép chuyên gia phù hợp"],
    "medical": ["logistics/lắp đặt phụ trợ nếu hợp pháp", "dịch vụ kỹ thuật được phép", "sourcing qua distributor đủ điều kiện"],
    "machinery": ["sourcing cấu hình", "lắp đặt/bảo trì", "đào tạo vận hành"],
    "construction": ["hạng mục thầu phụ nhỏ", "vật tư phụ trợ theo đơn", "dịch vụ theo địa bàn"],
    "other": ["phần việc tách được sau khi đọc HSMT", "sourcing không ôm vốn", "lead generation có buyer rõ"],
}


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def write(payload: dict) -> None:
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def rel_map(data: dict):
    return {x.get("tender_code"): x for x in data.get("open_tender_relationships", []) if x.get("tender_code")}


def partner_map(data: dict):
    return {x.get("partner_id"): x for x in data.get("partner_candidates", []) if x.get("partner_id")}


def match_map(data: dict):
    return {x.get("tender_code"): x for x in data.get("matches_by_open_tender", []) if x.get("tender_code")}


def relationship_for_partner(match: dict | None, partner_id: str):
    if not match:
        return None
    for item in match.get("same_buyer_candidates", []):
        if item.get("partner_id") == partner_id:
            return item
    return None


def dossier_counterparty(trigger: dict, candidate: dict, partner: dict, relationship: dict | None):
    category = trigger.get("procurement_category", "other")
    roles = ROLE_MAP.get(category, ROLE_MAP["other"])
    offers = OFFER_MAP.get(category, OFFER_MAP["other"])
    same_buyer_awards = int((relationship or {}).get("same_buyer_observed_awards") or 0)
    same_category_awards = int((relationship or {}).get("same_buyer_same_category_awards") or 0)

    why = [
        f"Match lịch sử cùng category: {candidate.get('match_score', 0)}/100.",
        f"Đã quan sát {candidate.get('observed_wins_same_category', 0)} KQLCNT thắng cùng nhóm.",
    ]
    if same_buyer_awards:
        why.append(f"Có {same_buyer_awards} award quan sát với chính buyer này; {same_category_awards} cùng category.")
    else:
        why.append("Chưa có same-buyer history trong sample; chỉ dùng như historical prime candidate cùng nhóm.")

    return {
        "partner_id": candidate.get("partner_id"),
        "contractor_name": candidate.get("contractor_name"),
        "contractor_code": candidate.get("contractor_code"),
        "tax_code": partner.get("tax_code"),
        "counterparty_score": min(100, int(candidate.get("match_score") or 0) + (8 if same_category_awards else 0)),
        "partner_evidence_score": partner.get("partner_evidence_score"),
        "observed_wins": partner.get("observed_wins"),
        "observed_wins_same_category": candidate.get("observed_wins_same_category"),
        "observed_winning_value_vnd": partner.get("observed_winning_value_vnd"),
        "buyers_observed": partner.get("buyers_observed", []),
        "same_buyer_observed_awards": same_buyer_awards,
        "same_buyer_same_category_awards": same_category_awards,
        "latest_win_at": candidate.get("latest_win_at"),
        "latest_tender_title": candidate.get("latest_tender_title"),
        "evidence_url": candidate.get("latest_source_url"),
        "why_this_counterparty": why,
        "target_roles_to_find": roles,
        "offers_to_test": offers,
        "contact_status": "unresolved",
        "verified_contact_paths": [],
        "contact_rule": "Chỉ thêm website/email/phone/person khi có nguồn công khai xác minh được; không suy đoán theo tên công ty hoặc domain.",
        "opening_hypothesis": f"Bên này đã có bằng chứng thắng nhóm {category}; kiểm tra xem họ có nhu cầu thuê ngoài {offers[0]} hoặc phần việc tương tự cho pipeline dự án hiện tại hay không.",
        "first_ask": "Xin trao đổi với người phụ trách dự án/BD phù hợp; chỉ hỏi về nhu cầu phần việc cụ thể, không tuyên bố biết họ đang dự gói hiện tại.",
        "kill_criteria": "Loại khỏi outreach nếu không xác minh được pháp nhân/kênh chính thức, năng lực hiện tại không còn phù hợp, hoặc không tìm thấy phần việc có thể cung cấp mà không ôm vốn lớn.",
    }


def build():
    now = datetime.now(timezone.utc)
    action = load(ACTION_PATH)
    partner_data = load(PARTNER_PATH)
    relationship_data = load(RELATIONSHIP_PATH)

    partners = partner_map(partner_data)
    matches = match_map(partner_data)
    relationships = rel_map(relationship_data)
    dossiers = []

    triggers = [x for x in action.get("buyer_triggers", []) if x.get("action_level") == "investigate_now"]
    for trigger in triggers:
        tender_code = trigger.get("tender_code")
        partner_match = matches.get(tender_code, {})
        relationship_match = relationships.get(tender_code)
        counterparties = []
        for candidate in partner_match.get("candidates", [])[:3]:
            partner = partners.get(candidate.get("partner_id"), {})
            relationship = relationship_for_partner(relationship_match, candidate.get("partner_id"))
            counterparties.append(dossier_counterparty(trigger, candidate, partner, relationship))

        route = trigger.get("recommended_path", "watch_only")
        if route == "subcontract_or_sourcing":
            first_move = "Điều tra tối đa 3 historical prime candidates; tìm đúng vai trò BD/project rồi chào một phần việc nhỏ có phạm vi và đơn vị giá rõ."
        elif route == "potential_prime_or_partner":
            first_move = "Đọc HSMT để xác minh eligibility trước. Song song điều tra partner candidates để tránh mặc định tự đứng prime khi chưa có lợi thế."
        else:
            first_move = "Chưa outreach cho đến khi xác định được phần việc tách được và counterparty hợp lý."

        dossiers.append({
            "tender_code": tender_code,
            "buyer": trigger.get("buyer"),
            "title": trigger.get("title"),
            "category": trigger.get("procurement_category"),
            "package_price_vnd": trigger.get("package_price_vnd"),
            "days_to_close": trigger.get("days_to_close"),
            "buyer_trigger_score": trigger.get("buyer_trigger_score"),
            "prime_fit_score": trigger.get("prime_fit_score"),
            "subcontract_fit_score": trigger.get("subcontract_fit_score"),
            "recommended_path": route,
            "official_source_url": trigger.get("official_verification_url") or trigger.get("source_url"),
            "counterparties": counterparties,
            "recommended_first_move": first_move,
            "success_signal_48h": "Có ít nhất 1 counterparty xác minh được yêu cầu trao đổi phạm vi, capability deck, báo giá sơ bộ hoặc chuyển tới đúng người phụ trách.",
            "kill_signal_48h": "Không xác minh được kênh chính thức, không có phần việc tách được, hoặc 3 counterparty phù hợp đều không cho thấy nhu cầu thương mại.",
        })

    verified = sum(len(c.get("verified_contact_paths", [])) for d in dossiers for c in d.get("counterparties", []))
    counterparties_total = sum(len(d.get("counterparties", [])) for d in dossiers)
    return {
        "meta": {
            "version": "1.5.0",
            "generated_at": now.isoformat(),
            "mode": "counterparty_execution_dossiers",
            "principle": "evidence_backed_counterparty_targets_with_no_fabricated_contacts",
        },
        "coverage": {
            "investigate_now_tenders": len(triggers),
            "dossiers_built": len(dossiers),
            "counterparty_targets": counterparties_total,
            "verified_contact_paths": verified,
            "unresolved_contact_targets": counterparties_total - verified,
        },
        "dossiers": dossiers,
        "warnings": [
            "Historical winner không đồng nghĩa bidder hiện tại.",
            "Contact unresolved là trạng thái hợp lệ; không sinh email/phone/person bằng suy đoán.",
            "Outreach chỉ nhằm kiểm chứng nhu cầu phần việc; không mua hàng hoặc cam kết vốn trước phản hồi thương mại thật.",
        ],
    }


def main():
    payload = build()
    write(payload)
    c = payload["coverage"]
    print(
        "counterparty-dossiers "
        f"tenders={c['dossiers_built']} targets={c['counterparty_targets']} "
        f"verified_contacts={c['verified_contact_paths']} unresolved={c['unresolved_contact_targets']}"
    )


if __name__ == "__main__":
    main()
