#!/usr/bin/env python3
"""Remove stale verified snapshots from current-state outputs.

The original observations remain in their source files for historical context. This
stage only removes their right to drive *current* Regional/Contradiction conclusions.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
FRESH = DATA / "freshness_state.json"
REGIONAL = DATA / "regional_intelligence.json"
CONTRADICTION = DATA / "contradiction_intelligence.json"
MONEY = DATA / "money_flow_intelligence.json"


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def save(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    fresh = load(FRESH, {}).get("datasets", {})
    regional = load(REGIONAL, {})
    contradiction = load(CONTRADICTION, {})
    money = load(MONEY, {})
    now = datetime.now(timezone.utc).isoformat()

    rstate = (fresh.get("regional") or {}).get("status")
    regional.setdefault("meta", {})["freshness_status"] = rstate
    regional["meta"]["trust_checked_at"] = now
    if rstate == "stale":
        regional["stale_regions"] = regional.get("regions", [])
        regional["regions"] = []
        regional["thesis"] = "Regional snapshot đã stale; giữ dữ liệu cũ làm historical context nhưng không dùng để mô tả trạng thái hiện tại."
        cov = regional.setdefault("coverage", {})
        cov["regions_current"] = 0
        cov["stale_snapshot_suppressed"] = True
    save(REGIONAL, regional)

    cstate = (fresh.get("contradiction") or {}).get("status")
    contradiction.setdefault("meta", {})["freshness_status"] = cstate
    contradiction["meta"]["trust_checked_at"] = now
    if cstate == "stale":
        score_map = {str(x.get("id") or x.get("theme_id")): int(x.get("score") or 0) for x in money.get("themes", []) if isinstance(x, dict)}
        for theme in contradiction.get("themes", []):
            tid = str(theme.get("theme_id") or "")
            theme["stale_counter_signals"] = theme.get("counter_signals", [])
            theme["counter_signals"] = []
            theme["counter_signal_count"] = 0
            theme["tension_level"] = "stale_counter_evidence_not_applied"
            if tid in score_map:
                theme["tension_adjusted_score"] = score_map[tid]
        contradiction["thesis"] = "Counter-signal snapshot đã stale; phản chứng cũ được giữ làm historical context nhưng không tiếp tục trừ điểm current thesis."
        contradiction.setdefault("coverage", {})["stale_snapshot_suppressed"] = True
    save(CONTRADICTION, contradiction)
    print(f"trust-staleness regional={rstate} contradiction={cstate}")


if __name__ == "__main__":
    main()
