#!/usr/bin/env python3
"""V1.6 Execution Loop: evidence-backed outreach packs for verified counterparties.

The module prepares, but never sends, outreach. Every pack must pass three gates:
1) current opportunity is still actionable;
2) counterparty has public evidence and a verified business contact path;
3) the user must confirm they can actually deliver the proposed offer.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
COUNTERPARTY_PATH = DATA / "counterparty_intelligence.json"
OFFICIAL_CONTACT_PATH = DATA / "official_contact_intelligence.json"
CONTACT_REGISTRY_PATH = DATA / "contact_registry.json"
OUTPUT_PATH = DATA / "outreach_intelligence.json"
MAX_PACKS = 12

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


def build():
    now = datetime.now(timezone.utc)
    counterparty = load(COUNTERPARTY_PATH)
    official = load(OFFICIAL_CONTACT_PATH)
    registry = load(CONTACT_REGISTRY_PATH)
    official_map = official_by_partner(official)
    registry_map = verified_registry_by_tax(registry)

    packs = []
    unresolved = []
    for dossier in counterparty.get("dossiers", []):
        for cp in dossier.get("counterparties", [])[:3]:
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
                    "reason": "no_verified_business_contact_path",
                })
                continue

            subject, body = outreach_draft(dossier, cp)
            pack = {
                "id": f"{dossier.get('tender_code')}::{cp.get('partner_id')}",
                "tender_code": dossier.get("tender_code"),
                "buyer": dossier.get("buyer"),
                "current_tender_title": dossier.get("title"),
                "category": dossier.get("category"),
                "package_price_vnd": dossier.get("package_price_vnd"),
                "days_to_close": dossier.get("days_to_close"),
                "recommended_path": dossier.get("recommended_path"),
                "official_tender_url": dossier.get("official_source_url"),
                "partner_id": cp.get("partner_id"),
                "contractor_name": cp.get("contractor_name"),
                "tax_code": cp.get("tax_code"),
                "counterparty_score": cp.get("counterparty_score"),
                "priority_score": priority_score(dossier, cp, len(contacts)),
                "verified_contact_paths": contacts,
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
                    "Gói/nhu cầu vẫn còn thời gian hợp lý; không tiếp cận nếu đã hết hạn hoặc quá sát hạn.",
                    "Contact path có nguồn công khai và đúng pháp nhân.",
                    "Nội dung không được nói hoặc ám chỉ rằng counterparty đang tham gia gói hiện tại nếu không có bằng chứng.",
                ],
                "success_signal": "Counterparty trả lời, chuyển đúng đầu mối, yêu cầu capability/rate card hoặc đồng ý trao đổi phạm vi thử.",
                "follow_up_rule": "Nếu không phản hồi, tối đa 1 follow-up ngắn sau 48–72 giờ; sau đó chuyển trạng thái Dead/No response thay vì spam.",
                "kill_criteria": cp.get("kill_criteria"),
                "default_stage": "ready_to_research",
            }
            packs.append(pack)

    packs.sort(key=lambda x: (x.get("priority_score", 0), x.get("days_to_close") or 0), reverse=True)
    packs = packs[:MAX_PACKS]
    return {
        "meta": {
            "version": "1.6.0",
            "generated_at": now.isoformat(),
            "mode": "human_in_the_loop_commercial_execution",
            "principle": "prepare_evidence_backed_outreach_never_auto_send_and_learn_from_real_responses",
        },
        "coverage": {
            "outreach_packs_ready": len(packs),
            "unique_counterparties_ready": len({x.get('partner_id') for x in packs}),
            "verified_contact_paths_in_ready_packs": sum(len(x.get("verified_contact_paths", [])) for x in packs),
            "unresolved_target_instances": len(unresolved),
        },
        "packs": packs,
        "unresolved": unresolved[:50],
        "stage_model": [
            "ready_to_research",
            "contacted",
            "replied",
            "qualified",
            "dead",
        ],
        "warnings": [
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
        f"ready={c['outreach_packs_ready']} counterparties={c['unique_counterparties_ready']} "
        f"paths={c['verified_contact_paths_in_ready_packs']} unresolved={c['unresolved_target_instances']}"
    )


if __name__ == "__main__":
    main()
