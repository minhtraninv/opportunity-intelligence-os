#!/usr/bin/env python3
"""Attach observed supply-side evidence to V2 money-flow themes.

This layer may promote a theme from unknown supply to `investigate_gap`, but never to
`confirmed_gap`. Confirmation requires broader supply proxies beyond procurement history.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MONEY = DATA / "money_flow_intelligence.json"
SUPPLY = DATA / "supply_side_intelligence.json"


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def main() -> None:
    money = load(MONEY)
    supply = load(SUPPLY)
    by_theme = supply.get("theme_supply_evidence", {}) if isinstance(supply.get("theme_supply_evidence"), dict) else {}

    attached = 0
    for theme in money.get("themes", []):
        theme_id = theme.get("id")
        observations = by_theme.get(theme_id, []) or []
        gap = theme.setdefault("supply_gap", {})
        gap["observed_supply_evidence"] = observations
        if observations:
            gap["status"] = "investigate_gap"
            gap["evidence_scope"] = "public_procurement_observed_vendor_depth_only"
            gap["caveat"] = (
                "Có dấu hiệu demand/capacity đáng điều tra trong mẫu mua sắm công; "
                "chưa đại diện toàn thị trường và chưa đủ để gọi là supply gap."
            )
            attached += 1
        else:
            gap["status"] = "unconfirmed_supply_gap"
            gap["evidence_scope"] = "no_qualified_supply_pressure_evidence_yet"

    money.setdefault("meta", {})["version"] = "2.1.0"
    money["meta"]["generated_at"] = datetime.now(timezone.utc).isoformat()
    money["meta"]["mode"] = "contextual_theme_chain_with_observed_supply_evidence"
    money["meta"]["principle"] = "supply_pressure_is_investigation_trigger_not_confirmed_gap"
    money.setdefault("coverage", {})["themes_with_observed_supply_pressure"] = attached
    money["coverage"]["supply_gaps_confirmed"] = 0
    guards = money.setdefault("guardrails", [])
    extra = "Procurement vendor-depth evidence can trigger investigation but cannot confirm a market-wide supply gap."
    if extra not in guards:
        guards.append(extra)

    MONEY.write_text(json.dumps(money, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"supply-gap enrich v2.1 attached_themes={attached} confirmed=0")


if __name__ == "__main__":
    main()
