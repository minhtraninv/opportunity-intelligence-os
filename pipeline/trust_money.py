#!/usr/bin/env python3
"""Trust-harden Money Flow output without expanding product scope.

The legacy theme engine is intentionally broad for discovery. This stage narrows what
may be published as directional intelligence: candidate headlines can add discovery
context, but only verified/curated non-procurement evidence can upgrade a theme.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PATH = DATA / "money_flow_intelligence.json"

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


def harden_theme(theme: dict) -> dict:
    evidence = [x for x in theme.get("evidence", []) if isinstance(x, dict)]
    verified = [x for x in evidence if x.get("quality") in VERIFIED_QUALITIES and x.get("family") != "procurement" and x.get("directional", True)]
    discovery = [x for x in evidence if x.get("quality") in DISCOVERY_QUALITIES and x.get("family") != "procurement"]
    procurement = [x for x in evidence if x.get("family") == "procurement"]

    verified_families = sorted({x.get("family") for x in verified if x.get("family") not in {None, "other", "market_data"}})
    verified_publishers = sorted({publisher(x) for x in verified if publisher(x) != "Unknown"})
    discovery_families = sorted({x.get("family") for x in discovery if x.get("family") not in {None, "other"}})
    discovery_publishers = sorted({publisher(x) for x in discovery if publisher(x) != "Unknown"})

    # Discovery can help prioritize research but cannot manufacture directional conviction.
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

    theme["score"] = score
    theme["status"] = status
    theme["verified_evidence_families"] = verified_families
    theme["verified_evidence_publishers"] = verified_publishers
    theme["discovery_evidence_families"] = discovery_families
    theme["verified_evidence_count"] = len(verified)
    theme["discovery_evidence_count"] = len(discovery)
    theme["procurement_support_count"] = len(procurement)
    theme["trust_reading"] = (
        "Directional status is gated by verified/curated non-procurement evidence. "
        "Official landing-page headlines and media remain discovery context only."
    )

    supply = theme.get("supply_gap") if isinstance(theme.get("supply_gap"), dict) else None
    if supply and status not in {"developing", "converging"} and supply.get("status") != "confirmed_gap":
        supply["status"] = "unconfirmed_supply_gap"
    return theme


def main() -> None:
    payload = load(PATH, {"themes": []})
    themes = [harden_theme(x) for x in payload.get("themes", []) if isinstance(x, dict)]
    themes.sort(key=lambda x: (-int(x.get("score") or 0), -len(x.get("verified_evidence_families") or []), str(x.get("label") or "")))
    payload["themes"] = themes

    strongest = next((x for x in themes if x.get("status") in {"converging", "developing"}), None)
    if strongest:
        payload["thesis"] = (
            f"Theme đáng điều tra nhất có verified convergence hiện tại: {strongest.get('label')} "
            f"({strongest.get('status')}; {len(strongest.get('verified_evidence_families') or [])} họ bằng chứng verified, "
            f"{len(strongest.get('verified_evidence_publishers') or [])} nhóm nguồn verified). "
            "Đây vẫn là research priority, không phải khuyến nghị hành động."
        )
    else:
        payload["thesis"] = (
            "Chưa có theme nào vượt verified evidence gate để được gọi là hội tụ. "
            "Discovery signals vẫn được lưu để theo dõi, nhưng hệ thống không ép chúng thành câu chuyện."
        )

    cov = payload.setdefault("coverage", {})
    cov["themes_converging"] = sum(1 for x in themes if x.get("status") == "converging")
    cov["themes_developing"] = sum(1 for x in themes if x.get("status") == "developing")
    cov["themes_with_verified_evidence"] = sum(1 for x in themes if int(x.get("verified_evidence_count") or 0) > 0)
    cov["themes_discovery_only"] = sum(1 for x in themes if int(x.get("verified_evidence_count") or 0) == 0 and int(x.get("discovery_evidence_count") or 0) > 0)

    meta = payload.setdefault("meta", {})
    meta["trust_patch"] = "3.0.1"
    meta["trust_hardened_at"] = datetime.now(timezone.utc).isoformat()
    meta["principle"] = "discovery_can_prioritize_research_but_cannot_create_directional_convergence"
    payload["guardrails"] = list(dict.fromkeys((payload.get("guardrails") or []) + [
        "Official-site headline discovery is not primary verified evidence.",
        "Developing/converging status requires verified non-procurement evidence families and independent institutions.",
    ]))
    save(PATH, payload)
    print(f"trust-money themes={len(themes)} converging={cov['themes_converging']} developing={cov['themes_developing']} verified={cov['themes_with_verified_evidence']}")


if __name__ == "__main__":
    main()
