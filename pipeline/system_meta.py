#!/usr/bin/env python3
"""Build one system-level version/status manifest from module metadata."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT = DATA / "system_meta.json"

MODULES = {
    "product_release": "product_release.json",
    "radar": "radar.json",
    "change_detector": "intelligence.json",
    "policy": "policy_intelligence.json",
    "freshness": "freshness_state.json",
    "methodology": "methodology_state.json",
    "money_flow": "money_flow_intelligence.json",
    "supply_side": "supply_side_intelligence.json",
    "regional": "regional_intelligence.json",
    "contradiction": "contradiction_intelligence.json",
    "lifecycle": "thesis_lifecycle.json",
    "entity_media": "entity_media_intelligence.json",
    "entity_convergence": "entity_convergence_intelligence.json",
    "source_coverage": "source_coverage_intelligence.json",
    "reports": "intelligence_reports.json",
    "trust_audit": "trust_audit.json",
    "procurement": "action_intelligence.json",
    "partner": "partner_intelligence.json",
    "relationship": "relationship_intelligence.json",
    "official_contact": "official_contact_intelligence.json",
    "counterparty": "counterparty_intelligence.json",
    "outreach": "outreach_intelligence.json",
    "personal_edge": "personal_edge_schema.json",
    "corporate": "corporate_intelligence.json"
}


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def version_tuple(value: str):
    nums = [int(x) for x in re.findall(r"\d+", str(value or ""))[:3]]
    return tuple((nums + [0, 0, 0])[:3])


def version_text(value: str) -> str | None:
    if not value:
        return None
    match = re.search(r"(\d+\.\d+(?:\.\d+)?)", str(value))
    return match.group(1) if match else None


def first_meta(payload: dict) -> dict:
    meta = payload.get("meta")
    return meta if isinstance(meta, dict) else {}


def main() -> None:
    components = {}
    versions = []
    newest = None
    baseline_status = "unknown"
    release_status = None

    for name, filename in MODULES.items():
        payload = load(DATA / filename)
        meta = first_meta(payload)
        version = version_text(meta.get("version") or payload.get("version") or payload.get("methodology_version"))
        generated = meta.get("generated_at") or meta.get("updated_at") or payload.get("updated_at") or payload.get("rebased_at")
        mode = meta.get("mode")
        status = meta.get("status")
        components[name] = {"version": version, "mode": mode, "status": status, "generated_at": generated}
        if name == "freshness":
            components[name]["datasets"] = {
                key: {
                    "status": row.get("status"),
                    "age_days": row.get("age_days"),
                    "updated_at": row.get("updated_at"),
                }
                for key, row in (payload.get("datasets") or {}).items()
                if isinstance(row, dict)
            }
        if name == "methodology":
            components[name]["methodology_version"] = payload.get("methodology_version")
        if version:
            versions.append(version)
        if name == "change_detector" and status:
            baseline_status = status
        if name == "product_release":
            release_status = status
        if generated:
            try:
                dt = datetime.fromisoformat(str(generated).replace("Z", "+00:00"))
                if newest is None or dt > newest:
                    newest = dt
            except Exception:
                pass

    system_version = max(versions, key=version_tuple) if versions else "0.0.0"
    if baseline_status == "active":
        baseline_label = "INTELLIGENCE ACTIVE"
    elif baseline_status == "warming_up":
        baseline_label = "LEARNING BASELINE"
    else:
        baseline_label = "SYSTEM ONLINE"

    release_label = "OFFICIAL" if release_status == "official" else "RC" if release_status == "release_candidate" else None
    trust_status = components.get("trust_audit", {}).get("status")
    trust_label = "TRUST PASS" if trust_status == "pass" else "TRUST UNKNOWN"
    status_label = f"{release_label} · {trust_label} · {baseline_label}" if release_label else f"{trust_label} · {baseline_label}"

    payload = {
        "system_version": system_version,
        "status_label": status_label,
        "release_status": release_status,
        "trust_status": trust_status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "latest_component_update": newest.isoformat() if newest else None,
        "components": components,
        "principle": "stable_release_plus_explicit_trust_freshness_and_methodology_boundaries"
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"system-meta version={system_version} status={status_label}")


if __name__ == "__main__":
    main()
