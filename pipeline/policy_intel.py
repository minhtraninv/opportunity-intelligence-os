#!/usr/bin/env python3
"""Build a policy intelligence layer for normal-person context.

Policy is treated as a leading context signal, not an instant opportunity.
Curated structural observations provide interpretation; fresh policy headlines from
history are surfaced separately and never auto-translated into money-making claims.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OBS_PATH = DATA / "policy_observations.json"
HISTORY_PATH = DATA / "history.json"
OUTPUT = DATA / "policy_intelligence.json"


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def main() -> None:
    obs = load(OBS_PATH, {}).get("observations", [])
    history = load(HISTORY_PATH, {}).get("events", [])

    policies = sorted(
        [x for x in obs if isinstance(x, dict)],
        key=lambda x: (-int(x.get("strategic_relevance") or 0), x.get("effective_from") or ""),
    )

    fresh = []
    curated_urls = {str(x.get("source_url") or "") for x in policies}
    seen = set()
    for event in reversed(history):
        if not isinstance(event, dict):
            continue
        if event.get("event_type") != "policy_regulation":
            continue
        if event.get("signal_quality") not in {"curated", "candidate"}:
            continue
        key = event.get("url") or event.get("id")
        if not key or key in seen or event.get("url") in curated_urls:
            continue
        seen.add(key)
        fresh.append({
            "id": event.get("id"),
            "title": event.get("title"),
            "publisher": event.get("publisher"),
            "source_url": event.get("url"),
            "categories": event.get("categories") or [],
            "geography": event.get("geography") or [],
            "signal_quality": event.get("signal_quality"),
            "first_seen_at": event.get("first_seen_at") or event.get("collected_at"),
            "interpretation_status": "needs_human_interpretation",
        })
        if len(fresh) >= 12:
            break

    top_channels = []
    channel_seen = set()
    for policy in policies:
        for channel in policy.get("money_flow_channels") or []:
            key = str(channel).casefold()
            if key not in channel_seen:
                channel_seen.add(key)
                top_channels.append(channel)

    thesis = (
        "Luật chơi 2026 đang nghiêng về giảm rào cản kinh doanh, thúc đẩy khu vực tư nhân, "
        "nâng chất lượng FDI/liên kết supplier và mở hành lang cho mô hình số mới. Chính sách "
        "là tín hiệu dẫn đường; chỉ nâng thành cơ hội khi dòng vốn, buyer và hành vi thực tế xác nhận."
    )

    payload = {
        "meta": {
            "version": "2.5.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "policy_context_and_rules_of_the_game",
            "principle": "policy_is_leading_context_not_instant_opportunity",
        },
        "thesis": thesis,
        "coverage": {
            "curated_structural_policies": len(policies),
            "fresh_policy_signals_needing_interpretation": len(fresh),
            "money_flow_channels": len(top_channels),
        },
        "structural_policies": policies,
        "fresh_policy_signals": fresh,
        "money_flow_channels": top_channels[:12],
        "reading_rule": (
            "Đọc policy theo chuỗi: văn bản -> cơ chế thực thi -> dòng vốn/hành vi -> buyer -> "
            "supply response. Không nhảy từ văn bản thẳng sang kết luận đầu tư/kinh doanh."
        ),
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"policy-intel structural={len(policies)} fresh={len(fresh)} "
        f"channels={len(top_channels)}"
    )


if __name__ == "__main__":
    main()
