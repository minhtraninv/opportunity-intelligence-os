#!/usr/bin/env python3
"""V2.3 Contradiction Intelligence.

Every strong theme must carry counter-signals and explicit falsification conditions.
This module does not 'average away' contradictions; it surfaces them and applies a
small confidence haircut only when they directly constrain the thesis.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCE = DATA / "contradiction_observations.json"
MONEY = DATA / "money_flow_intelligence.json"
REGIONAL = DATA / "regional_intelligence.json"
OUT = DATA / "contradiction_intelligence.json"

SEVERITY_WEIGHT = {"low": 5, "medium": 10, "high": 18}


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def main() -> None:
    source = load(SOURCE)
    money = load(MONEY)
    regional = load(REGIONAL)

    by_theme: dict[str, list[dict]] = defaultdict(list)
    for x in source.get("observations", []):
        for theme in x.get("themes", []):
            by_theme[theme].append(x)

    regional_divergences = []
    for row in regional.get("regions", []):
        if row.get("state") == "production_strong_capital_cooling":
            regional_divergences.append({
                "region": row.get("region"),
                "state": row.get("state"),
                "iip_7m_yoy_pct": row.get("iip_7m_yoy_pct"),
                "fdi_yoy_pct": row.get("fdi_yoy_pct"),
                "interpretation": row.get("interpretation"),
            })

    theme_rows = []
    for theme in money.get("themes", []):
        theme_id = theme.get("id")
        counters = by_theme.get(theme_id, [])
        severity_points = sum(SEVERITY_WEIGHT.get(x.get("severity"), 0) for x in counters)
        high_count = sum(1 for x in counters if x.get("severity") == "high")
        medium_count = sum(1 for x in counters if x.get("severity") == "medium")

        if high_count >= 1 or severity_points >= 35:
            tension = "high"
        elif medium_count >= 2 or severity_points >= 18:
            tension = "material"
        elif counters:
            tension = "watch"
        else:
            tension = "no_verified_counter_signal"

        original_score = int(theme.get("score") or 0)
        haircut = min(15, severity_points // 3)
        adjusted = max(0, original_score - haircut)

        theme_rows.append({
            "theme_id": theme_id,
            "theme_label": theme.get("label"),
            "original_score": original_score,
            "tension_level": tension,
            "counter_signal_count": len(counters),
            "confidence_haircut": haircut,
            "tension_adjusted_score": adjusted,
            "counter_signals": counters,
            "falsification_conditions": [x.get("falsifies_if") for x in counters if x.get("falsifies_if")],
            "rule": "Điểm sau phản chứng chỉ giảm độ tự tin vào narrative; không phải xác suất lợi nhuận hay tín hiệu bán/mua."
        })

    theme_rows.sort(key=lambda x: (-x["counter_signal_count"], -x["original_score"], x["theme_label"] or ""))

    payload = {
        "meta": {
            "version": "2.3.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "counter_signal_and_falsification_intelligence",
            "principle": "strong_theses_must_survive_counter_evidence"
        },
        "coverage": {
            "verified_counter_signals": len(source.get("observations", [])),
            "themes_with_counter_signals": sum(1 for x in theme_rows if x["counter_signal_count"] > 0),
            "regional_production_capital_divergences": len(regional_divergences),
        },
        "themes": theme_rows,
        "regional_divergences": regional_divergences,
        "guardrails": [
            "Counter-signals limit a thesis; they do not automatically reverse it.",
            "A tension-adjusted score is an investigation-confidence aid, not an expected-return estimate.",
            "Registered FDI, realized FDI, production and local supplier capture are different layers and must not be conflated.",
            "Regional divergences are hypotheses about mechanism (new capital vs installed-base ramp-up), not causal proof."
        ]
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"contradiction v2.3 signals={payload['coverage']['verified_counter_signals']} "
        f"themes={payload['coverage']['themes_with_counter_signals']} regional_div={len(regional_divergences)}"
    )


if __name__ == "__main__":
    main()
