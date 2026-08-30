#!/usr/bin/env python3
"""Trust-harden Money Flow output without expanding product scope.

The legacy theme engine is intentionally broad for discovery. This stage narrows what
may be published as directional intelligence: candidate headlines can add discovery
context, but only fresh verified/curated non-procurement evidence can upgrade a theme.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PATH = DATA / "money_flow_intelligence.json"
FRESHNESS = DATA / "freshness_state.json"

VERIFIED_QUALITIES = {"official_verified", "curated", "primary_verified"}
DISCOVERY_QUALITIES = {"candidate", "official_headline_discovery", "media_discovery"}


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def save(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def publisher(item: dict) -> str:
    return str(item.get("publisher_group") or item.get("publisher") or "Unknown").strip()


def apply_freshness(evidence: list[dict], freshness: dict) -> list[dict]:
    macro_status = str((freshness.get("macro") or {}).get("status") or "unknown")
    output = []
    for raw in evidence:
        item = dict(raw)
        if str(item.get("id") or "").startswith("macro::"):
            item["snapshot_freshness"] = macro_status
            if macro_status == "stale":
                if item.get("quality") == "official_verified":
                    item["quality"] = "historical_verified"
                item["directional"] = False
                item["freshness_note"] = "Verified snapshot is stale; retained as historical context only."
            elif macro_status == "unknown":
                if item.get("quality") == "official_verified":
                    item["quality"] = "historical_unaged"
                item["directional"] = False
                item["freshness_note"] = "Snapshot age is unknown; it cannot create current directional conviction."
            elif macro_status == "aging":
                item["freshness_note"] = "Snapshot is aging but remains inside the current-use window."
        output.append(item)
    return output


def harden_theme(theme: dict, freshness: dict) -> dict:
    evidence = apply_freshness(
        [x for x in theme.get("evidence", []) if isinstance(x, dict)], freshness
    )
    theme["evidence"] = evidence

    verified = [
        x for x in evidence
        if x.get("quality") in VERIFIED_QUALITIES
        and x.get("family") != "procurement"
        and x.get("directional", True)
    ]
    discovery = [
        x for x in evidence
        if x.get("quality") in DISCOVERY_QUALITIES
        and x.get("family") != "procurement"
    ]
    procurement = [x for x in evidence if x.get("family") == "procurement"]

    verified_families = sorted({x.get("family") for x in verified if x.get("family") not in {None, "other", "market_data"}})
    verified_publishers = sorted({publisher(x) for x in verified if publisher(x) != "Unknown"})
    discovery_families = sorted({x.get("family") for x in discovery if x.get("family") not in {None, "other"}})
    discovery_publishers = sorted({publisher(x) for x in discovery if publisher(x) != "Unknown"})

    score = 10
    score += min(4, len(verified_families)) * 13
    score += min(3, len(verified_publishers)) * 7
    score += min(3, len(discovery_families)) * 2
    score += min(2, len(discovery_publishers))
    score += min(2, len(procurement))
    score = min(88, score)

    if len(verified_families) >= 3 and len(verified_publishers) >= 2:
        status = "converging"
    elif len(verified_families) >= 2 and len(verified_publishers) >= 2:
        status = "developing"
    elif len(verified_families) >= 1:
        status = "early"
    else:
        status = "insufficient"
        score = min(score, 29)

    # Preserve broad discovery metadata, but public/lifecycle family counts are verified-only.
    theme["all_observed_families"] = list(theme.get("independent_families") or [])
    theme["all_observed_publishers"] = list(theme.get("independent_publishers") or [])
    theme["independent_families"] = verified_families
    theme["independent_publishers"] = verified_publishers
    theme["non_procurement_publishers"] = verified_publishers
    theme["score"] = score
    theme["status"] = status
    theme["verified_evidence_families"] = verified_families
    theme["verified_evidence_publishers"] = verified_publishers
    theme["discovery_evidence_families"] = discovery_families
    theme["discovery_evidence_publishers"] = discovery_publishers
    theme["verified_evidence_count"] = len(verified)
    theme["discovery_evidence_count"] = len(discovery)
    theme["procurement_support_count"] = len(procurement)
    theme["directional_evidence_count"] = len(verified)
    theme["snapshot_freshness"] = {"macro": (freshness.get("macro") or {}).get("status", "unknown")}
    theme["trust_reading"] = (
        "Directional status and public family/publisher counts are gated by fresh verified/curated "
        "non-procurement evidence. Official headlines, media and stale verified snapshots remain context only."
    )

    supply = theme.get("supply_gap") if isinstance(theme.get("supply_gap"), dict) else None
    if supply and status not in {"developing", "converging"} and supply.get("status") != "confirmed_gap":
        supply["status"] = "unconfirmed_supply_gap"
    return theme


def main() -> None:
    payload = load(PATH, {"themes": []})
    fresh_payload = load(FRESHNESS, {})
    freshness = fresh_payload.get("datasets", {}) if isinstance(fresh_payload.get("datasets"), dict) else {}
    themes = [harden_theme(x, freshness) for x in payload.get("themes", []) if isinstance(x, dict)]
    themes.sort(key=lambda x: (-int(x.get("score") or 0), -len(x.get("verified_evidence_families") or []), str(x.get("label") or "")))
    payload["themes"] = themes

    strongest = next((x for x in themes if x.get("status") in {"converging", "developing"}), None)
    if strongest:
        payload["thesis"] = (
            f"Theme đáng điều tra nhất có fresh verified convergence hiện tại: {strongest.get('label')} "
            f"({strongest.get('status')}; {len(strongest.get('verified_evidence_families') or [])} họ bằng chứng verified, "
            f"{len(strongest.get('verified_evidence_publishers') or [])} nhóm nguồn verified). "
            "Đây vẫn là research priority, không phải khuyến nghị hành động."
        )
    else:
        payload["thesis"] = (
            "Chưa có theme nào vượt fresh verified evidence gate để được gọi là hội tụ. "
            "Discovery hoặc historical signals vẫn được lưu để theo dõi, nhưng hệ thống không ép chúng thành câu chuyện hiện tại."
        )

    cov = payload.setdefault("coverage", {})
    cov["themes_converging"] = sum(1 for x in themes if x.get("status") == "converging")
    cov["themes_developing"] = sum(1 for x in themes if x.get("status") == "developing")
    cov["themes_with_verified_evidence"] = sum(1 for x in themes if int(x.get("verified_evidence_count") or 0) > 0)
    cov["themes_discovery_only"] = sum(1 for x in themes if int(x.get("verified_evidence_count") or 0) == 0 and int(x.get("discovery_evidence_count") or 0) > 0)
    cov["macro_snapshot_freshness"] = (freshness.get("macro") or {}).get("status", "unknown")

    meta = payload.setdefault("meta", {})
    meta["trust_patch"] = "3.0.1"
    meta["trust_hardened_at"] = datetime.now(timezone.utc).isoformat()
    meta["snapshot_freshness"] = {k: (v or {}).get("status") for k, v in freshness.items() if isinstance(v, dict)}
    meta["principle"] = "discovery_or_stale_verified_context_can_prioritize_research_but_cannot_create_directional_convergence"
    payload["guardrails"] = list(dict.fromkeys((payload.get("guardrails") or []) + [
        "Official-site headline discovery is not primary verified evidence.",
        "Developing/converging status requires fresh verified non-procurement evidence families and independent institutions.",
        "Public family/publisher counts exclude discovery-only evidence so Lifecycle cannot mistake discovery breadth for verified breadth.",
        "A verified snapshot loses current-directional authority when it becomes stale or its age is unknown."
    ]))
    save(PATH, payload)
    print(
        f"trust-money themes={len(themes)} converging={cov['themes_converging']} "
        f"developing={cov['themes_developing']} verified={cov['themes_with_verified_evidence']} "
        f"macro_freshness={cov['macro_snapshot_freshness']}"
    )


if __name__ == "__main__":
    main()
