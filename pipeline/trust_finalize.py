#!/usr/bin/env python3
"""Finalize public intelligence under V3.0.1 trust boundaries.

This stage is deliberately conservative. It keeps broad discovery data in the repo,
but public-facing convergence and primary-domain coverage only receive credit for
evidence that actually crossed a verification boundary.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CONVERGENCE = DATA / "entity_convergence_intelligence.json"
MEDIA = DATA / "entity_media_intelligence.json"
COVERAGE = DATA / "source_coverage_intelligence.json"
RAW = DATA / "raw_feed.json"
REGISTRY = DATA / "source_registry.json"

DISCOVERY_DOMAINS = {"media_discovery", "entity_discovery"}


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def save(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def is_true_primary(evidence: dict) -> bool:
    origin = evidence.get("origin")
    quality = evidence.get("quality")
    if origin == "official_corporate_disclosure":
        return True
    if origin == "normalized_public_signal" and quality == "curated":
        return True
    return False


def harden_convergence() -> dict:
    payload = load(CONVERGENCE, {"entities": []})
    media = load(MEDIA, {})
    typed = {
        str(x.get("id")): x for x in media.get("auto_entities", [])
        if isinstance(x, dict) and x.get("id")
    }

    verified_entities = []
    discovery_candidates = []
    verified_watchlist = []
    suppressed = []

    for row in payload.get("entities", []):
        if not isinstance(row, dict):
            continue
        entity_id = str(row.get("entity_id") or "")
        media_entity = typed.get(entity_id, {})
        if row.get("entity_origin") == "auto_discovered":
            etype = media_entity.get("entity_type") or row.get("entity_type")
            eligible = bool(media_entity.get("eligible_for_entity_convergence", etype == "organization_candidate"))
            row["entity_type"] = etype
            if not eligible or etype != "organization_candidate":
                suppressed.append({
                    "entity_id": entity_id,
                    "label": row.get("label"),
                    "entity_type": etype,
                    "reason": media_entity.get("suppression_reason") or "not_an_organization_candidate",
                })
                continue

        evidence = [x for x in row.get("evidence", []) if isinstance(x, dict)]
        for ev in evidence:
            if ev.get("origin") == "normalized_public_signal" and ev.get("quality") == "candidate":
                ev["origin"] = "official_headline_discovery"
                ev["evidence_grade"] = "official_headline_discovery"
            elif is_true_primary(ev):
                ev["evidence_grade"] = "primary_verified"
            elif ev.get("origin") == "media_discovery":
                ev["evidence_grade"] = "media_discovery"

        primary = [x for x in evidence if is_true_primary(x)]
        discovery = [x for x in evidence if not is_true_primary(x)]
        verified_families = sorted({x.get("family") for x in primary if x.get("family") and x.get("family") != "procurement"})
        discovery_families = sorted({x.get("family") for x in discovery if x.get("family") and x.get("family") != "procurement"})
        all_families = sorted(set(verified_families + discovery_families))
        publishers = sorted({str(x.get("publisher")) for x in evidence if x.get("publisher")})

        score = min(100,
            len(verified_families) * 20
            + min(3, len(primary)) * 8
            + max(0, min(3, len(publishers) - 1)) * 4
            + min(3, len(discovery_families)) * 3
        )

        if score >= 72 and len(primary) >= 2 and len(verified_families) >= 2 and len(all_families) >= 3 and len(publishers) >= 2:
            status = "high_convergence"
        elif score >= 48 and len(primary) >= 1 and len(verified_families) >= 1 and len(all_families) >= 2 and len(publishers) >= 2:
            status = "converging"
        elif len(primary) >= 1:
            status = "verified_watch"
        elif len(discovery_families) >= 2 and len(publishers) >= 2:
            status = "discovery_convergence"
            score = min(score, 39)
        else:
            status = "watch"
            score = min(score, 29)

        row["status"] = status
        row["convergence_score"] = score
        row["primary_evidence_count"] = len(primary)
        row["media_evidence_count"] = sum(1 for x in evidence if x.get("origin") == "media_discovery")
        row["official_headline_discovery_count"] = sum(1 for x in evidence if x.get("origin") == "official_headline_discovery")
        row["verified_evidence_families"] = verified_families
        row["discovery_evidence_families"] = discovery_families
        row["evidence_families"] = all_families
        row["evidence"] = evidence
        row["trust_reading"] = "Only converging/high_convergence rows cross the public primary-evidence gate."

        if status in {"high_convergence", "converging"}:
            verified_entities.append(row)
        elif status == "verified_watch":
            verified_watchlist.append(row)
        elif status == "discovery_convergence":
            discovery_candidates.append(row)

    verified_entities.sort(key=lambda x: (int(x.get("convergence_score") or 0), int(x.get("primary_evidence_count") or 0)), reverse=True)
    discovery_candidates.sort(key=lambda x: (int(x.get("convergence_score") or 0), int(x.get("media_evidence_count") or 0)), reverse=True)
    verified_watchlist.sort(key=lambda x: int(x.get("convergence_score") or 0), reverse=True)

    payload["entities"] = verified_entities[:30]
    payload["discovery_candidates"] = discovery_candidates[:30]
    payload["verified_watchlist"] = verified_watchlist[:30]
    payload["suppressed_non_organizations"] = suppressed[:50]
    payload["coverage"] = {
        **(payload.get("coverage") or {}),
        "public_verified_entities": len(verified_entities),
        "discovery_candidates": len(discovery_candidates),
        "verified_watchlist": len(verified_watchlist),
        "suppressed_non_organizations": len(suppressed),
        "high_convergence": sum(1 for x in verified_entities if x.get("status") == "high_convergence"),
        "converging": sum(1 for x in verified_entities if x.get("status") == "converging"),
    }
    payload.setdefault("meta", {})["trust_patch"] = "3.0.1"
    payload["meta"]["trust_hardened_at"] = datetime.now(timezone.utc).isoformat()
    payload["reading_rule"] = (
        "Public Entity Convergence contains only rows with true primary evidence and cross-family confirmation. "
        "Media/headline-only candidates remain available separately for discovery and cannot pose as verified convergence."
    )
    save(CONVERGENCE, payload)
    return payload


def harden_coverage() -> dict:
    payload = load(COVERAGE, {"domains": [], "source_health": []})
    raw = load(RAW, {})
    registry = load(REGISTRY, {"sources": [], "domains": []})
    raw_items = [x for x in raw.get("items", []) if isinstance(x, dict)]
    curated = Counter(x.get("source_id") for x in raw_items if x.get("signal_quality") == "curated")
    candidates = Counter(x.get("source_id") for x in raw_items if x.get("signal_quality") == "candidate")

    source_map = {str(x.get("id")): x for x in payload.get("source_health", []) if isinstance(x, dict)}
    registry_sources = {str(x.get("id")): x for x in registry.get("sources", []) if isinstance(x, dict)}

    for sid, row in source_map.items():
        spec = registry_sources.get(sid, row)
        collector = spec.get("collector")
        old_evidence = int(row.get("evidence_items_this_run") or 0)
        if collector == "main":
            verified = int(curated.get(sid, 0))
            discovery = int(candidates.get(sid, 0))
        elif collector in {"corporate", "procurement"}:
            verified = old_evidence
            discovery = 0
        elif collector == "entity_media":
            verified = 0
            discovery = old_evidence
        else:
            verified = 0
            discovery = old_evidence if collector != "planned" else 0
        row["verified_evidence_items_this_run"] = verified
        row["discovery_evidence_items_this_run"] = discovery
        row["evidence_items_this_run"] = verified if collector not in {"entity_media"} else discovery

    domains_out = []
    for domain in registry.get("domains", []):
        if not isinstance(domain, dict):
            continue
        did = domain.get("id")
        relevant = [source_map.get(str(s.get("id"))) for s in registry.get("sources", []) if did in (s.get("domains") or [])]
        relevant = [x for x in relevant if x]
        active = [x for x in relevant if x.get("status") != "planned"]
        healthy = [x for x in active if x.get("health") == "ok"]
        broken = [x for x in active if x.get("health") == "error"]
        target = int(domain.get("target_healthy_sources") or 1)
        discovery_domain = did in DISCOVERY_DOMAINS
        productive = [x for x in healthy if int(x.get("discovery_evidence_items_this_run") if discovery_domain else x.get("verified_evidence_items_this_run") or 0) > 0]
        verified_productive = [x for x in healthy if int(x.get("verified_evidence_items_this_run") or 0) > 0]
        discovery_productive = [x for x in healthy if int(x.get("discovery_evidence_items_this_run") or 0) > 0]

        if not active:
            status = "missing"
        elif not healthy and broken:
            status = "broken"
        elif len(productive) >= target:
            status = "strong"
        elif productive:
            status = "partial"
        else:
            status = "weak"

        note = {
            "strong": "Đủ số nguồn đang tạo evidence đúng cấp cho mục đích của domain; vẫn phải kiểm tra freshness và độc lập.",
            "partial": "Đã có evidence đúng cấp nhưng chưa đủ số nguồn độc lập theo target.",
            "weak": "Có nguồn/collector nhưng chưa tạo evidence đủ cấp để nâng độ tin cậy.",
            "broken": "Nguồn active đang lỗi và chưa có coverage thay thế đủ dùng.",
            "missing": "Chưa có collector active; đây là blind spot thực sự.",
        }[status]
        planned = [x.get("name") for x in relevant if x.get("status") == "planned"][:3]
        domains_out.append({
            **domain,
            "status": status,
            "active_sources": len(active),
            "healthy_sources": len(healthy),
            "productive_sources": len(productive),
            "verified_productive_sources": len(verified_productive),
            "discovery_productive_sources": len(discovery_productive),
            "broken_sources": len(broken),
            "verified_evidence_items_this_run": sum(int(x.get("verified_evidence_items_this_run") or 0) for x in verified_productive),
            "discovery_evidence_items_this_run": sum(int(x.get("discovery_evidence_items_this_run") or 0) for x in discovery_productive),
            "evidence_items_this_run": sum(int(x.get("discovery_evidence_items_this_run") if discovery_domain else x.get("verified_evidence_items_this_run") or 0) for x in productive),
            "healthy_source_names": [x.get("name") for x in healthy],
            "productive_source_names": [x.get("name") for x in productive],
            "broken_source_names": [x.get("name") for x in broken],
            "planned_next_sources": planned,
            "coverage_note": note,
            "evidence_standard": "discovery" if discovery_domain else "verified_primary",
        })

    severity = {"missing": 5, "broken": 4, "weak": 3, "partial": 2, "strong": 1}
    domains_out.sort(key=lambda x: (int(x.get("priority") or 9), -severity.get(x.get("status"), 0), str(x.get("label") or "")))
    counts = Counter(x.get("status") for x in domains_out)
    blind = [x for x in domains_out if x.get("status") != "strong"]

    verified_source_count = sum(1 for x in source_map.values() if x.get("health") == "ok" and int(x.get("verified_evidence_items_this_run") or 0) > 0)
    discovery_source_count = sum(1 for x in source_map.values() if x.get("health") == "ok" and int(x.get("discovery_evidence_items_this_run") or 0) > 0)
    payload["domains"] = domains_out
    payload["source_health"] = list(source_map.values())
    payload["coverage"] = {
        **(payload.get("coverage") or {}),
        "domains": len(domains_out),
        "strong": counts.get("strong", 0),
        "partial": counts.get("partial", 0),
        "weak": counts.get("weak", 0),
        "broken": counts.get("broken", 0),
        "missing": counts.get("missing", 0),
        "verified_productive_sources": verified_source_count,
        "discovery_productive_sources": discovery_source_count,
        "productive_sources": verified_source_count,
    }
    payload["critical_blind_spots"] = [{
        "domain_id": x.get("id"), "label": x.get("label"), "status": x.get("status"),
        "priority": x.get("priority"), "why": x.get("why"), "coverage_note": x.get("coverage_note"),
        "planned_next_sources": x.get("planned_next_sources") or [], "evidence_standard": x.get("evidence_standard")
    } for x in blind[:8]]
    payload.setdefault("meta", {})["trust_patch"] = "3.0.1"
    payload["meta"]["trust_hardened_at"] = datetime.now(timezone.utc).isoformat()
    payload["thesis"] = (
        "Primary-domain coverage is now credited only for verified evidence. Headline/media discovery is measured separately. "
        "A lower coverage score is preferable to false confidence."
    )
    payload["reading_rule"] = (
        "STRONG means enough sources produce evidence at the domain's required grade: verified primary for economic domains, "
        "discovery-grade for discovery domains. Official landing-page headlines alone cannot make a primary domain STRONG."
    )
    save(COVERAGE, payload)
    return payload


def main() -> None:
    conv = harden_convergence()
    cov = harden_coverage()
    print(
        f"trust-finalize verified_entities={len(conv.get('entities', []))} discovery_candidates={len(conv.get('discovery_candidates', []))} "
        f"coverage_strong={cov.get('coverage', {}).get('strong', 0)} verified_sources={cov.get('coverage', {}).get('verified_productive_sources', 0)}"
    )


if __name__ == "__main__":
    main()
