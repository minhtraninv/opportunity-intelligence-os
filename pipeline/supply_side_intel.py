#!/usr/bin/env python3
"""V2.1 observed supply-side intelligence.

This module measures *observed public-procurement market depth* only. It must not be
interpreted as total market supply. Thin history is explicitly reported as unknown,
never as scarcity.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "supply_side_intelligence.json"

THEME_MAP = {
    "digital_services": "data_infrastructure",
    "logistics": "logistics_trade",
}


def load(name: str, default):
    try:
        value = json.loads((DATA / name).read_text(encoding="utf-8"))
        return value
    except Exception:
        return default


def confidence(awards: int, vendors: int, buyers: int) -> tuple[str, int]:
    if awards >= 40 and vendors >= 12 and buyers >= 10:
        return "moderate", 70
    if awards >= 20 and vendors >= 8 and buyers >= 6:
        return "low_moderate", 55
    if awards >= 10 and vendors >= 5:
        return "low", 40
    return "thin_history", 20


def hhi(counts: Counter) -> float | None:
    total = sum(counts.values())
    if total <= 0:
        return None
    return round(sum((v / total) ** 2 for v in counts.values()), 4)


def pressure_status(open_count: int, vendor_count: int, award_count: int, conf: str, top_share: float | None) -> str:
    if open_count <= 0:
        return "no_current_demand_observed"
    if conf == "thin_history":
        return "thin_history_not_gap"
    ratio = open_count / max(vendor_count, 1)
    if conf in {"moderate", "low_moderate"} and ratio >= 0.75 and (top_share or 0) >= 0.25:
        return "investigate_capacity_pressure"
    if ratio >= 0.4:
        return "watch_demand_vs_observed_supply"
    return "observed_supply_depth_present"


def main() -> None:
    action = load("action_intelligence.json", {})
    history = load("partner_history.json", {})

    open_by_cat = defaultdict(list)
    for x in action.get("buyer_triggers", []):
        category = x.get("procurement_category") or "other"
        open_by_cat[category].append(x)

    awards_by_cat = defaultdict(list)
    for x in history.get("items", []):
        if x.get("record_type") != "award_winner_observation":
            continue
        category = x.get("procurement_category") or "other"
        awards_by_cat[category].append(x)

    categories = sorted(set(open_by_cat) | set(awards_by_cat))
    rows = []
    theme_evidence = defaultdict(list)

    for category in categories:
        open_items = open_by_cat[category]
        awards = awards_by_cat[category]
        vendor_counts = Counter(
            (x.get("contractor_code") or x.get("tax_code") or x.get("contractor_name"))
            for x in awards
            if (x.get("contractor_code") or x.get("tax_code") or x.get("contractor_name"))
        )
        buyers_hist = {x.get("buyer") for x in awards if x.get("buyer")}
        buyers_open = {x.get("buyer") for x in open_items if x.get("buyer")}
        award_count = len(awards)
        vendor_count = len(vendor_counts)
        buyer_count = len(buyers_hist)
        conf, conf_score = confidence(award_count, vendor_count, buyer_count)
        total_wins = sum(vendor_counts.values())
        top_share = round(max(vendor_counts.values()) / total_wins, 3) if total_wins and vendor_counts else None
        prices = [float(x.get("package_price_vnd")) for x in open_items if isinstance(x.get("package_price_vnd"), (int, float)) and x.get("package_price_vnd") > 0]
        overlap = len(buyers_hist & buyers_open)
        status = pressure_status(len(open_items), vendor_count, award_count, conf, top_share)

        row = {
            "category": category,
            "theme_id": THEME_MAP.get(category),
            "current_demand": {
                "open_tenders": len(open_items),
                "unique_buyers": len(buyers_open),
                "package_value_sum_vnd": round(sum(prices), 0) if prices else None,
                "median_package_value_vnd": round(median(prices), 0) if prices else None,
            },
            "observed_supply_history": {
                "award_observations": award_count,
                "unique_vendors": vendor_count,
                "unique_buyers": buyer_count,
                "top_vendor_win_share": top_share,
                "winner_hhi": hhi(vendor_counts),
                "current_buyers_seen_in_history": overlap,
            },
            "sample_confidence": conf,
            "confidence_score": conf_score,
            "pressure_status": status,
            "interpretation": (
                "Chỉ là độ sâu vendor quan sát được trong mẫu KQLCNT hiện đã backfill; "
                "không đại diện toàn bộ nguồn cung thị trường."
            ),
        }
        rows.append(row)

        theme = THEME_MAP.get(category)
        if theme and status == "investigate_capacity_pressure" and conf in {"moderate", "low_moderate"}:
            theme_evidence[theme].append({
                "category": category,
                "status": status,
                "confidence": conf,
                "open_tenders": len(open_items),
                "observed_unique_vendors": vendor_count,
                "award_observations": award_count,
                "top_vendor_win_share": top_share,
            })

    rows.sort(key=lambda x: (-x["current_demand"]["open_tenders"], -x["confidence_score"], x["category"]))
    payload = {
        "meta": {
            "version": "2.1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "observed_public_procurement_supply_depth",
            "principle": "thin_history_is_unknown_not_scarcity"
        },
        "coverage": {
            "categories": len(rows),
            "award_observations": sum(len(v) for v in awards_by_cat.values()),
            "open_tenders": sum(len(v) for v in open_by_cat.values()),
            "categories_with_moderate_or_better_confidence": sum(1 for x in rows if x["sample_confidence"] == "moderate"),
            "capacity_pressure_candidates": sum(1 for x in rows if x["pressure_status"] == "investigate_capacity_pressure"),
        },
        "categories": rows,
        "theme_supply_evidence": dict(theme_evidence),
        "guardrails": [
            "This is public-procurement observed supply, not total market supply.",
            "Thin history cannot be interpreted as a supply shortage.",
            "Winner concentration can reflect specialization, buyer mix or sampling bias; it is not proof of market power.",
            "No category is promoted to confirmed supply gap by this module alone."
        ]
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"supply-side v2.1 categories={len(rows)} awards={payload['coverage']['award_observations']} "
        f"open={payload['coverage']['open_tenders']} pressure={payload['coverage']['capacity_pressure_candidates']}"
    )


if __name__ == "__main__":
    main()
