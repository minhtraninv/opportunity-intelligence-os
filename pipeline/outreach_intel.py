#!/usr/bin/env python3
"""V1.6.1 Execution Loop with campaign-level deduplication.

The module prepares, but never sends, outreach. It collapses multiple current tender
signals into one counterparty+category campaign so the UI does not mistake repeated
market signals for repeated independent leads or encourage spam.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
COUNTERPARTY_PATH = DATA / "counterparty_intelligence.json"
OFFICIAL_CONTACT_PATH = DATA / "official_contact_intelligence.json"
CONTACT_REGISTRY_PATH = DATA / "contact_registry.json"
OUTPUT_PATH = DATA / "outreach_intelligence.json"
MAX_CAMPAIGNS = 12
MAX_RELATED_OPPORTUNITIES = 5

CATEGORY_LABELS = {
    "digital_services": "số hóa / phần mềm / dịch vụ số",
    "office_goods": "thiết bị / hàng văn phòng",
    "printing_media": "in ấn / truyền thông",
    "maintenance": "bảo trì / facility",
    "garment_ppe": "đồng phục / PPE",
    "food_services": "thực phẩm / suất ăn",
    "logistics": "logistics / vận chuyển",
    "consulting": "tư vấn",
    "medical": "y tế",
    "machinery": "máy móc / thiết bị",
    "construction": "xây dựng",
    "other": "dịch vụ / cung ứng",
}


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def verified_registry_by_tax(registry: dict):
    result = {}
    for entity in registry.get("entities", []):
        tax = str(entity.get("tax_code") or "").strip()
        if not tax or entity.get("identity_status") != "verified":
            continue
        paths = []
        for item in entity.get("contacts", []):
            if item.get("status") != "verified" or not item.get("value") or not item.get("source_url"):
                continue
            paths.append({
                "type": item.get("type"),
                "value": item.get("value"),
                "scope": item.get("scope"),
                "source_url": item.get("source_url"),
                "source_type": item.get("source_type"),
            })
        if paths:
            result[tax] = paths
    return result


def official_by_partner(data: dict):
    return {
        x.get("partner_id"): x.get("contact_paths", [])
        for x in data.get("contacts", [])
        if x.get("partner_id") and x.get("contact_paths")
    }


def merge_paths(*groups):
    seen = set()
    out = []
    for group in groups:
        for item in group or []:
            key = (str(item.get("type") or "").lower(), str(item.get("value") or "").lower())
            if not item.get("value") or key in seen:
                continue
            seen.add(key)
            out.append(item)
    return out


def priority_score(dossier: dict, cp: dict, contact_count: int):
    score = int(cp.get("counterparty_score") or 0)
    score += round(int(dossier.get("subcontract_fit_score") or 0) * 0.18)
    if dossier.get("recommended_path") == "subcontract_or_sourcing":
        score += 7
    if cp.get("same_buyer_same_category_awards"):
        score += 8
    score += min(6, contact_count * 2)
    days = dossier.get("days_to_close")
    if isinstance(days, (int, float)) and 3 <= days <= 14:
        score += 5
    return min(100, score)


def outreach_draft(dossier: dict, cp: dict):
    company = cp.get("contractor_name") or "Quý công ty"
    category = CATEGORY_LABELS.get(dossier.get("category"), dossier.get("category") or "dự án")
    historical = cp.get("latest_tender_title") or "một gói cùng nhóm"
    offer = (cp.get("offers_to_test") or ["một phần việc có thể bóc tách"])[0]
    subject = f"Đề xuất hỗ trợ phần việc {category} — cần xác minh nhu cầu"
    body = (
        f"Chào anh/chị,\n\n"
        f"Tôi đang tìm hiểu khả năng hợp tác với các đơn vị đã có kinh nghiệm triển khai {category} cho khu vực công. "
        f"Theo KQLCNT công khai, {company} từng được ghi nhận thắng gói “{historical}”.\n\n"
        f"Tôi muốn kiểm tra xem đội dự án của anh/chị hiện có nhu cầu thuê ngoài / tìm đối tác cho phần việc: {offer}. "
        f"Nếu phù hợp, tôi có thể gửi một phạm vi thử nhỏ và cách tính đơn giá để hai bên đánh giá trước khi cam kết lớn.\n\n"
        f"[CHỈ GỬI SAU KHI BẠN ĐIỀN BẰNG CHỨNG NĂNG LỰC THẬT CỦA MÌNH Ở ĐÂY]\n\n"
        f"Nếu đây không phải đầu mối phù hợp, nhờ anh/chị chuyển giúp tới người phụ trách BD / dự án / sourcing. Cảm ơn anh/chị."
    )
    return subject, body


def opportunity_ref(dossier: dict):
    return {
        "tender_code": dossier.get("tender_code"),
        "buyer": dossier.get("buyer"),
        "title": dossier.get("title"),
        "package_price_vnd": dossier.get("package_price_vnd"),
        "days_to_close": dossier.get("days_to_close"),
        "recommended_path": dossier.get("recommended_path"),
        "official_tender_url": dossier.get("official_source_url"),
    }


def build():
    now = datetime.now(timezone.utc)
    counterparty = load(COUNTERPARTY_PATH)
    official = load(OFFICIAL_CONTACT_PATH)
    registry = load(CONTACT_REGISTRY_PATH)
    official_map = official_by_partner(official)
    registry_map = verified_registry_by_tax(registry)

    grouped = defaultdict(list)
    unresolved = []
    candidate_instances = 0

    for dossier in counterparty.get("dossiers", []):
        for cp in dossier.get("counterparties", [])[:3]:
            candidate_instances += 1
            contacts = merge_paths(
                cp.get("verified_contact_paths", []),
                official_map.get(cp.get("partner_id"), []),
                registry_map.get(str(cp.get("tax_code") or "").strip(), []),
            )
            if not contacts:
                unresolved.append({
                    "tender_code": dossier.get("tender_code"),
                    "partner_id": cp.get("partner_id"),
                    "contractor_name": cp.get("contractor_name"),
                    "category": dossier.get("category"),
                    "reason": "no_verified_business_contact_path",
                })
                continue

            category = dossier.get("category") or "other"
            key = (cp.get("partner_id"), category)
            grouped[key].append({
                "dossier": dossier,
                "counterparty": cp,
                "contacts": contacts,
                "priority": priority_score(dossier, cp, len(contacts)),
            })

    campaigns = []
    for (partner_id, category), instances in grouped.items():
        instances.sort(key=lambda x: (x["priority"], x["dossier"].get("days_to_close") or 0), reverse=True)
        best = instances[0]
        dossier = best["dossier"]
        cp = best["counterparty"]
        contacts = merge_paths(*(x["contacts"] for x in instances))
        subject, body = outreach_draft(dossier, cp)

        related = []
        seen_tenders = set()
        for item in instances:
            ref = opportunity_ref(item["dossier"])
            code = ref.get("tender_code")
            if not code or code in seen_tenders:
                continue
            seen_tenders.add(code)
            related.append(ref)
            if len(related) >= MAX_RELATED_OPPORTUNITIES:
                break

        campaigns.append({
            "id": f"{partner_id}::{category}",
            "campaign_type": "counterparty_category",
            "partner_id": partner_id,
            "contractor_name": cp.get("contractor_name"),
            "tax_code": cp.get("tax_code"),
            "category": category,
            "category_label": CATEGORY_LABELS.get(category, category),
            "priority_score": best["priority"],
            "counterparty_score": cp.get("counterparty_score"),
            "verified_contact_paths": contacts,
            "related_opportunity_count": len({x["dossier"].get("tender_code") for x in instances if x["dossier"].get("tender_code")}),
            "related_opportunities": related,
            "primary_tender_code": dossier.get("tender_code"),
            "primary_buyer": dossier.get("buyer"),
            "primary_tender_title": dossier.get("title"),
            "primary_package_price_vnd": dossier.get("package_price_vnd"),
            "primary_days_to_close": dossier.get("days_to_close"),
            "primary_official_tender_url": dossier.get("official_source_url"),
            "recommended_path": dossier.get("recommended_path"),
            "historical_evidence": {
                "latest_win_title": cp.get("latest_tender_title"),
                "latest_evidence_url": cp.get("evidence_url"),
                "observed_wins_same_category": cp.get("observed_wins_same_category"),
                "same_buyer_same_category_awards": cp.get("same_buyer_same_category_awards"),
            },
            "offer_to_validate": (cp.get("offers_to_test") or [None])[0],
            "target_roles": cp.get("target_roles_to_find", []),
            "outreach_subject_draft": subject,
            "outreach_body_draft": body,
            "send_gates": [
                "Bạn thực sự có năng lực cung cấp offer đã nêu hoặc có partner thật để thực hiện.",
                "Có ít nhất một market signal liên quan còn đủ thời gian để kiểm chứng; không dùng tender đã hết hạn làm lý do tạo urgency giả.",
                "Contact path có nguồn công khai và đúng pháp nhân.",
                "Nội dung không được nói hoặc ám chỉ rằng counterparty đang tham gia bất kỳ gói hiện tại nào nếu không có bằng chứng.",
                "Chỉ một outreach cho campaign này; không gửi email riêng cho từng tender signal cùng một counterparty.",
            ],
            "success_signal": "Counterparty trả lời, chuyển đúng đầu mối, yêu cầu capability/rate card hoặc đồng ý trao đổi phạm vi thử.",
            "follow_up_rule": "Nếu không phản hồi, tối đa 1 follow-up ngắn sau 48–72 giờ; sau đó chuyển trạng thái Dead/No response thay vì spam.",
            "kill_criteria": cp.get("kill_criteria"),
            "default_stage": "ready_to_research",
        })

    campaigns.sort(key=lambda x: (x.get("priority_score", 0), x.get("related_opportunity_count", 0)), reverse=True)
    campaigns = campaigns[:MAX_CAMPAIGNS]
    unique_paths = {
        (str(path.get("type") or "").lower(), str(path.get("value") or "").lower())
        for campaign in campaigns
        for path in campaign.get("verified_contact_paths", [])
        if path.get("value")
    }
    return {
        "meta": {
            "version": "1.6.1",
            "generated_at": now.isoformat(),
            "mode": "human_in_the_loop_deduplicated_counterparty_campaigns",
            "principle": "one_counterparty_category_campaign_can_absorb_multiple_market_signals_no_fake_lead_multiplication",
        },
        "coverage": {
            "candidate_target_instances": candidate_instances,
            "campaigns_ready": len(campaigns),
            "unique_counterparties_ready": len({x.get("partner_id") for x in campaigns}),
            "related_opportunity_signals_in_campaigns": sum(x.get("related_opportunity_count", 0) for x in campaigns),
            "unique_verified_contact_paths": len(unique_paths),
            "unresolved_target_instances": len(unresolved),
            "unique_unresolved_counterparties": len({x.get("partner_id") for x in unresolved if x.get("partner_id")}),
        },
        "packs": campaigns,
        "unresolved": unresolved[:50],
        "stage_model": [
            "ready_to_research",
            "contacted",
            "replied",
            "qualified",
            "dead",
        ],
        "warnings": [
            "Một campaign có thể chứa nhiều tender signals; không diễn giải số signal thành số lead độc lập.",
            "Draft không được gửi nếu placeholder năng lực thật chưa được thay thế.",
            "Historical award evidence không chứng minh counterparty đang dự gói hiện tại.",
            "Không tự động gửi email; hệ thống giữ human-in-the-loop để tránh spam và tuyên bố sai.",
        ],
    }


def main():
    payload = build()
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    c = payload["coverage"]
    print(
        "outreach-intel "
        f"campaigns={c['campaigns_ready']} counterparties={c['unique_counterparties_ready']} "
        f"signals={c['related_opportunity_signals_in_campaigns']} unique_paths={c['unique_verified_contact_paths']} "
        f"unresolved={c['unresolved_target_instances']}"
    )


if __name__ == "__main__":
    main()
