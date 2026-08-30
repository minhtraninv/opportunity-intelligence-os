#!/usr/bin/env python3
"""V1.4 Buyer ↔ Vendor Relationship Intelligence.

This stage derives market-channel evidence from official historical award observations.
It must never be interpreted as evidence of favoritism, collusion, or current bidding.
A repeated edge only means the buyer-vendor pair appears repeatedly in the award sample
collected by this project.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTNER_HISTORY = ROOT / "data" / "partner_history.json"
ACTION_INTELLIGENCE = ROOT / "data" / "action_intelligence.json"
OUTPUT_PATH = ROOT / "data" / "relationship_intelligence.json"

EDGE_LIMIT = 300
BUYER_LIMIT = 150
OPEN_MATCH_LIMIT = 5


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def norm(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def key_text(value) -> str:
    value = norm(value).casefold()
    value = re.sub(r"[^\wÀ-ỹ]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def partner_key(event: dict) -> str:
    return norm(event.get("contractor_code")) or key_text(event.get("contractor_name"))


def edge_id(buyer_key: str, vendor_key: str) -> str:
    return hashlib.sha1(f"{buyer_key}|{vendor_key}".encode("utf-8")).hexdigest()[:20]


def numeric_values(events, field):
    values = []
    for event in events:
        value = event.get(field)
        if isinstance(value, (int, float)) and value >= 0:
            values.append(value)
    return values


def recency_score(latest_at, captured_at):
    latest = parse_dt(latest_at)
    if not latest:
        return 0
    age = captured_at - latest
    if age <= timedelta(days=30):
        return 12
    if age <= timedelta(days=90):
        return 8
    if age <= timedelta(days=365):
        return 4
    return 0


def build_edges(history: dict, captured_at: datetime):
    grouped = defaultdict(list)
    for event in history.get("items", []):
        buyer = norm(event.get("buyer"))
        vendor = norm(event.get("contractor_name"))
        bkey = key_text(buyer)
        vkey = partner_key(event)
        if not buyer or not vendor or not bkey or not vkey:
            continue
        grouped[(bkey, vkey)].append(event)

    edges = []
    for (bkey, vkey), events in grouped.items():
        events.sort(key=lambda x: x.get("award_public_at") or x.get("first_seen_at") or "", reverse=True)
        latest = events[0]
        categories = Counter(x.get("procurement_category", "other") for x in events)
        prices = numeric_values(events, "winning_price_vnd")
        count = len(events)
        repeat_bonus = min(26, max(0, count - 1) * 10)
        diversity_bonus = min(6, max(0, len(categories) - 1) * 2)
        score = min(95, 48 + repeat_bonus + diversity_bonus + recency_score(latest.get("award_public_at"), captured_at))
        edges.append({
            "relationship_id": edge_id(bkey, vkey),
            "buyer_key": bkey,
            "buyer": latest.get("buyer"),
            "partner_id": vkey,
            "contractor_name": latest.get("contractor_name"),
            "contractor_code": latest.get("contractor_code"),
            "tax_code": latest.get("tax_code"),
            "observed_awards": count,
            "observed_award_value_vnd": sum(prices) if prices else None,
            "categories": [name for name, _ in categories.most_common()],
            "category_counts": dict(categories),
            "latest_award_at": latest.get("award_public_at"),
            "latest_tender_code": latest.get("tender_code"),
            "latest_tender_title": latest.get("tender_title"),
            "latest_source_url": latest.get("source_url"),
            "relationship_evidence_score": score,
            "relationship_signal": "repeated_observed_awards" if count >= 2 else "single_observed_award",
            "caveat": "Chỉ phản ánh KQLCNT quan sát được trong mẫu; không chứng minh ưu ái, bidder hiện tại hoặc khả năng thắng tương lai.",
            "examples": [{
                "tender_code": x.get("tender_code"),
                "title": x.get("tender_title"),
                "category": x.get("procurement_category"),
                "winning_price_vnd": x.get("winning_price_vnd"),
                "award_public_at": x.get("award_public_at"),
                "source_url": x.get("source_url"),
            } for x in events[:4]],
        })

    edges.sort(key=lambda x: (
        x.get("relationship_evidence_score", 0),
        x.get("observed_awards", 0),
        x.get("latest_award_at") or "",
    ), reverse=True)
    return edges[:EDGE_LIMIT]


def build_buyer_profiles(edges: list[dict]):
    grouped = defaultdict(list)
    for edge in edges:
        grouped[edge.get("buyer_key")].append(edge)

    profiles = []
    for bkey, buyer_edges in grouped.items():
        buyer_edges.sort(key=lambda x: (x.get("observed_awards", 0), x.get("relationship_evidence_score", 0)), reverse=True)
        total_awards = sum(int(x.get("observed_awards", 0)) for x in buyer_edges)
        top_awards = int(buyer_edges[0].get("observed_awards", 0)) if buyer_edges else 0
        categories = Counter()
        for edge in buyer_edges:
            categories.update(edge.get("category_counts", {}))
        concentration = round(top_awards / total_awards, 3) if total_awards else None
        profiles.append({
            "buyer_key": bkey,
            "buyer": buyer_edges[0].get("buyer") if buyer_edges else bkey,
            "observed_awards": total_awards,
            "unique_observed_partners": len(buyer_edges),
            "top_partner_award_share": concentration,
            "repeated_partner_relationships": sum(1 for x in buyer_edges if x.get("observed_awards", 0) >= 2),
            "category_counts": dict(categories),
            "top_partners": [{
                "partner_id": x.get("partner_id"),
                "contractor_name": x.get("contractor_name"),
                "observed_awards": x.get("observed_awards"),
                "observed_award_value_vnd": x.get("observed_award_value_vnd"),
                "categories": x.get("categories"),
                "latest_award_at": x.get("latest_award_at"),
                "relationship_evidence_score": x.get("relationship_evidence_score"),
                "latest_source_url": x.get("latest_source_url"),
            } for x in buyer_edges[:5]],
            "sample_warning": "Vendor concentration chỉ tính trên award sample đã thu được, không phải toàn bộ lịch sử mua sắm của buyer.",
        })

    profiles.sort(key=lambda x: (x.get("observed_awards", 0), x.get("unique_observed_partners", 0)), reverse=True)
    return profiles[:BUYER_LIMIT]


def open_tender_matches(action_data: dict, edges: list[dict]):
    by_buyer = defaultdict(list)
    for edge in edges:
        by_buyer[edge.get("buyer_key")].append(edge)

    output = []
    for trigger in action_data.get("buyer_triggers", []):
        bkey = key_text(trigger.get("buyer"))
        category = trigger.get("procurement_category", "other")
        candidates = []
        for edge in by_buyer.get(bkey, []):
            category_awards = int(edge.get("category_counts", {}).get(category, 0))
            same_category = category_awards > 0
            score = int(edge.get("relationship_evidence_score", 0))
            if same_category:
                score = min(95, score + 12 + min(10, category_awards * 3))
            else:
                score = max(0, score - 12)
            candidates.append({
                "partner_id": edge.get("partner_id"),
                "contractor_name": edge.get("contractor_name"),
                "contractor_code": edge.get("contractor_code"),
                "same_buyer_observed_awards": edge.get("observed_awards"),
                "same_buyer_same_category_awards": category_awards,
                "same_category": same_category,
                "observed_award_value_vnd": edge.get("observed_award_value_vnd"),
                "latest_award_at": edge.get("latest_award_at"),
                "latest_tender_title": edge.get("latest_tender_title"),
                "latest_source_url": edge.get("latest_source_url"),
                "relationship_match_score": score,
                "caveat": edge.get("caveat"),
            })
        candidates.sort(key=lambda x: (
            x.get("same_category", False),
            x.get("relationship_match_score", 0),
            x.get("same_buyer_observed_awards", 0),
        ), reverse=True)
        candidates = candidates[:OPEN_MATCH_LIMIT]

        best = candidates[0] if candidates else None
        if best and best.get("same_category"):
            if trigger.get("recommended_path") == "subcontract_or_sourcing":
                route = "same_buyer_partner_first"
                note = "Có historical vendor cùng buyer + cùng category trong sample: ưu tiên kiểm tra họ như một đường subcontract/sourcing trước khi tự đứng prime."
            else:
                route = "incumbent_check_before_prime"
                note = "Có historical vendor cùng buyer + cùng category: kiểm tra cạnh tranh/incumbent trước khi bỏ thời gian vào đường prime."
        elif best:
            route = "buyer_familiar_vendor_context"
            note = "Có vendor từng bán cho buyer nhưng khác category; dùng làm context về kênh mua, không coi là đối tác phù hợp mặc định."
        else:
            route = "no_same_buyer_history_in_sample"
            note = "Chưa thấy lịch sử buyer-vendor trong sample; đây là thiếu dữ liệu, không phải bằng chứng buyer chưa có incumbent."

        output.append({
            "tender_code": trigger.get("tender_code"),
            "buyer": trigger.get("buyer"),
            "category": category,
            "recommended_path": trigger.get("recommended_path"),
            "relationship_route": route,
            "relationship_note": note,
            "same_buyer_candidates": candidates,
        })
    return output


def build_output(history: dict, action_data: dict, captured_at: datetime):
    edges = build_edges(history, captured_at)
    buyers = build_buyer_profiles(edges)
    matches = open_tender_matches(action_data, edges)
    repeated_edges = sum(1 for x in edges if x.get("observed_awards", 0) >= 2)
    open_same_buyer = sum(bool(x.get("same_buyer_candidates")) for x in matches)
    open_same_buyer_category = sum(
        bool(x.get("same_buyer_candidates") and x["same_buyer_candidates"][0].get("same_category"))
        for x in matches
    )
    return {
        "meta": {
            "version": "1.4.1",
            "generated_at": iso(captured_at),
            "mode": "buyer_vendor_relationship_intelligence",
            "principle": "observed_award_relationship_is_market_channel_evidence_not_wrongdoing",
        },
        "coverage": {
            "award_events_used": len(history.get("items", [])),
            "buyer_vendor_edges": len(edges),
            "repeated_edges": repeated_edges,
            "buyer_profiles": len(buyers),
            "open_tenders_with_same_buyer_history": open_same_buyer,
            "open_tenders_with_same_buyer_same_category_history": open_same_buyer_category,
        },
        "relationship_edges": edges,
        "buyer_profiles": buyers,
        "open_tender_relationships": matches,
        "warnings": [
            "Đây là quan hệ award quan sát được trong sample KQLCNT, không phải toàn bộ lịch sử mua sắm.",
            "Lặp lại buyer-vendor không chứng minh ưu ái, thông đồng hay bidder hiện tại.",
            "Same-buyer history dùng để chọn thứ tự điều tra kênh bán/đối tác và đánh giá cạnh tranh, không dùng để kết luận kết quả gói đang mở.",
        ],
    }


def main():
    captured = now_utc()
    history = load_json(PARTNER_HISTORY, {"version": 1, "items": []})
    action_data = load_json(ACTION_INTELLIGENCE, {})
    output = build_output(history, action_data, captured)
    write_json(OUTPUT_PATH, output)
    c = output["coverage"]
    print(
        "relationship-intel "
        f"events={c['award_events_used']} edges={c['buyer_vendor_edges']} repeated={c['repeated_edges']} "
        f"buyers={c['buyer_profiles']} same_buyer_open={c['open_tenders_with_same_buyer_history']} "
        f"same_category_open={c['open_tenders_with_same_buyer_same_category_history']}"
    )


if __name__ == "__main__":
    main()
