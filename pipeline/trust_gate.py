#!/usr/bin/env python3
"""Fail publication when V3.0.1 trust invariants are violated."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "trust_audit.json"


def load(name: str, default):
    try:
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    except Exception:
        return default


def main() -> None:
    money = load("money_flow_intelligence.json", {})
    conv = load("entity_convergence_intelligence.json", {})
    coverage = load("source_coverage_intelligence.json", {})
    reports = load("intelligence_reports.json", {})
    media = load("entity_media_intelligence.json", {})
    release = load("product_release.json", {})

    errors = []
    checks = []

    def check(name: str, ok: bool, detail: str):
        checks.append({"name": name, "passed": bool(ok), "detail": detail})
        if not ok:
            errors.append(f"{name}: {detail}")

    bad_theme = []
    for t in money.get("themes", []):
        if t.get("status") in {"developing", "converging"}:
            vf = len(t.get("verified_evidence_families") or [])
            vp = len(t.get("verified_evidence_publishers") or [])
            minimum = 3 if t.get("status") == "converging" else 2
            if vf < minimum or vp < 2:
                bad_theme.append(f"{t.get('id')}:{t.get('status')} vf={vf} vp={vp}")
    check("money_flow_verified_gate", not bad_theme, "; ".join(bad_theme) or "all directional theme states have verified family + institution support")

    bad_entities = []
    for e in conv.get("entities", []):
        if e.get("status") not in {"converging", "high_convergence"} or int(e.get("primary_evidence_count") or 0) < 1:
            bad_entities.append(f"{e.get('label')}:{e.get('status')}:primary={e.get('primary_evidence_count')}")
        if e.get("entity_origin") == "auto_discovered" and e.get("entity_type") != "organization_candidate":
            bad_entities.append(f"{e.get('label')}:auto_type={e.get('entity_type')}")
    check("entity_publication_gate", not bad_entities, "; ".join(bad_entities) or "public convergence contains only primary-verified organization rows")

    bad_discovery = []
    media_types = {str(x.get("id")): x for x in media.get("auto_entities", []) if isinstance(x, dict)}
    for e in conv.get("discovery_candidates", []):
        if e.get("entity_origin") == "auto_discovered":
            row = media_types.get(str(e.get("entity_id")), {})
            if row.get("entity_type") != "organization_candidate" or not row.get("eligible_for_entity_convergence"):
                bad_discovery.append(str(e.get("label")))
    check("open_world_entity_type_gate", not bad_discovery, ", ".join(bad_discovery) or "locations/public bodies are excluded from organization convergence")

    bad_domains = []
    for d in coverage.get("domains", []):
        if d.get("status") != "strong":
            continue
        target = int(d.get("target_healthy_sources") or 1)
        if d.get("evidence_standard") == "discovery":
            productive = int(d.get("discovery_productive_sources") or 0)
        else:
            productive = int(d.get("verified_productive_sources") or 0)
        if productive < target:
            bad_domains.append(f"{d.get('id')}:productive={productive}<target={target}")
    check("source_coverage_grade_gate", not bad_domains, "; ".join(bad_domains) or "STRONG domains meet their required evidence grade")

    bad_reports = []
    for kind in ("weekly", "monthly"):
        report = (reports.get("reports") or {}).get(kind, {})
        ready = bool((report.get("history_readiness") or {}).get("history_ready"))
        if not ready:
            if report.get("analysis_status") != "locked_learning_history":
                bad_reports.append(f"{kind}:not_locked")
            if report.get("what_changed") or report.get("entity_watch") or report.get("regional_watch"):
                bad_reports.append(f"{kind}:analysis_not_empty_while_locked")
    daily = (reports.get("reports") or {}).get("daily", {})
    for e in daily.get("entity_watch", []):
        if int(e.get("primary_evidence") or 0) < 1:
            bad_reports.append(f"daily_entity_without_primary:{e.get('label')}")
    check("report_maturity_gate", not bad_reports, "; ".join(bad_reports) or "period reports respect history readiness and entity verification")

    release_version = str((release.get("meta") or {}).get("version") or "")
    check("release_version_gate", release_version == "3.0.1", f"product_release={release_version or 'missing'}")

    payload = {
        "meta": {
            "version": "3.0.1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "prepublication_trust_gate",
            "status": "pass" if not errors else "fail",
        },
        "checks": checks,
        "error_count": len(errors),
        "errors": errors,
        "principle": "publish_less_rather_than_publish_unearned_confidence",
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if errors:
        raise RuntimeError("Trust gate failed:\n- " + "\n- ".join(errors))
    print(f"trust-gate PASS checks={len(checks)}")


if __name__ == "__main__":
    main()
