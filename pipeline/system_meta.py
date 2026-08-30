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
    "radar": "radar.json",
    "change_detector": "intelligence.json",
    "policy": "policy_intelligence.json",
    "money_flow": "money_flow_intelligence.json",
    "supply_side": "supply_side_intelligence.json",
    "regional": "regional_intelligence.json",
    "contradiction": "contradiction_intelligence.json",
    "lifecycle": "thesis_lifecycle.json",
    "entity_convergence": "entity_convergence_intelligence.json",
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

    for name, filename in MODULES.items():
        payload = load(DATA / filename)
        meta = first_meta(payload)
        version = version_text(meta.get("version") or payload.get("version"))
        generated = meta.get("generated_at") or meta.get("updated_at") or payload.get("updated_at")
        mode = meta.get("mode")
        status = meta.get("status")
        components[name] = {"version": version, "mode": mode, "status": status, "generated_at": generated}
        if version:
            versions.append(version)
        if name == "change_detector" and status:
            baseline_status = status
        if generated:
            try:
                dt = datetime.fromisoformat(str(generated).replace("Z", "+00:00"))
                if newest is None or dt > newest:
                    newest = dt
            except Exception:
                pass

    system_version = max(versions, key=version_tuple) if versions else "0.0.0"
    if baseline_status == "active":
        status_label = "INTELLIGENCE ACTIVE"
    elif baseline_status == "warming_up":
        status_label = "LEARNING BASELINE"
    else:
        status_label = "SYSTEM ONLINE"

    payload = {
        "system_version": system_version,
        "status_label": status_label,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "latest_component_update": newest.isoformat() if newest else None,
        "components": components,
        "principle": "system_version_is_derived_from_module_versions_not_hardcoded_in_frontend"
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"system-meta version={system_version} status={status_label}")


if __name__ == "__main__":
    main()
