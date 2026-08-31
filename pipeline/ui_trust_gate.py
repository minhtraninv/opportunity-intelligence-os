#!/usr/bin/env python3
"""Public UI/data contract gate for Opportunity Intelligence OS.

This gate protects the user-facing research contract rather than scoring methodology.
A public conclusion must be traceable, identifiers must join deterministically, and
frontend asset versions must be coherent so a deploy cannot silently mix old/new code.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
VERIFIED_QUALITIES = {"official_verified", "curated", "primary_verified"}
DIRECTIONAL_STATES = {"developing", "converging", "high_convergence"}


def load(name: str, default=None):
    if default is None:
        default = {}
    try:
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    except Exception:
        return default


def has_http(url) -> bool:
    return isinstance(url, str) and url.startswith(("https://", "http://"))


def main() -> None:
    errors: list[str] = []
    notes: list[str] = []

    macro = load("macro_observations.json")
    policy = load("policy_intelligence.json")
    money = load("money_flow_intelligence.json")
    regional = load("regional_intelligence.json")
    contradiction = load("contradiction_intelligence.json")
    convergence = load("entity_convergence_intelligence.json")
    frontier = load("frontier_intelligence.json")

    # 1) Every public macro/policy observation must be directly traceable.
    for row in macro.get("observations", []):
        if not has_http(row.get("source_url")):
            errors.append(f"macro provenance missing: {row.get('id') or row.get('title')}")
    for row in policy.get("structural_policies", []):
        if not has_http(row.get("source_url")):
            errors.append(f"policy provenance missing: {row.get('id') or row.get('title')}")

    # 2) Money Flow and Contradiction must join on a stable theme identifier.
    themes = money.get("themes", [])
    theme_ids = [str(t.get("id") or t.get("theme_id") or "") for t in themes]
    if any(not x for x in theme_ids):
        errors.append("money-flow theme without id/theme_id")
    if len(theme_ids) != len(set(theme_ids)):
        errors.append("duplicate money-flow theme ids")
    contradiction_ids = {str(x.get("theme_id") or "") for x in contradiction.get("themes", []) if x.get("theme_id")}
    orphan = sorted(contradiction_ids - set(theme_ids))
    if orphan:
        errors.append(f"contradiction theme ids not present in Money Flow: {', '.join(orphan)}")

    # 3) A directional Money Flow state requires verified evidence with usable provenance.
    for t in themes:
        tid = str(t.get("id") or t.get("theme_id") or "")
        verified = [
            e for e in (t.get("evidence") or [])
            if isinstance(e, dict)
            and e.get("quality") in VERIFIED_QUALITIES
            and e.get("family") != "procurement"
            and e.get("directional") is not False
        ]
        if t.get("status") in DIRECTIONAL_STATES:
            if not verified:
                errors.append(f"directional Money Flow without verified evidence: {tid}")
            if not any(has_http(e.get("source_url")) for e in verified):
                errors.append(f"directional Money Flow without source URL: {tid}")
        declared = t.get("verified_evidence_families") or t.get("independent_families") or []
        observed = {e.get("family") for e in verified if e.get("family")}
        if t.get("status") in DIRECTIONAL_STATES and declared and not set(declared).issubset(observed):
            errors.append(f"Money Flow declared families exceed verified evidence: {tid}")

    # 4) Regional claims must carry direct source links. Dual acceleration needs both legs.
    for r in regional.get("regions", []):
        ev = r.get("evidence") or {}
        iip, fdi = ev.get("iip_source_url"), ev.get("fdi_source_url")
        if r.get("iip_7m_yoy_pct") is not None and not has_http(iip):
            errors.append(f"regional IIP source missing: {r.get('region')}")
        if r.get("fdi_yoy_pct") is not None and not has_http(fdi):
            errors.append(f"regional FDI source missing: {r.get('region')}")
        if r.get("state") == "dual_acceleration" and not (has_http(iip) and has_http(fdi)):
            errors.append(f"dual_acceleration without both source legs: {r.get('region')}")

    # 5) Published entity convergence must remain auditable to at least one source.
    for e in convergence.get("entities", []):
        if e.get("status") == "not_observed":
            continue
        evidence = [x for x in (e.get("evidence") or []) if isinstance(x, dict)]
        if not evidence or not any(has_http(x.get("source_url")) for x in evidence):
            errors.append(f"published entity without auditable evidence: {e.get('label')}")

    # 6) Every active counter-signal shown publicly must be traceable.
    for t in contradiction.get("themes", []):
        for c in t.get("counter_signals", []) or []:
            if isinstance(c, dict) and not has_http(c.get("source_url")):
                errors.append(f"counter-signal source missing: {c.get('id') or c.get('title')}")

    # 7) Discovery Frontier is allowed to be broad only if it stays explicitly discovery-only
    # and every surfaced candidate can be drilled back to source evidence.
    for c in frontier.get("attention_queue", []):
        cid = c.get("id") or c.get("label")
        if c.get("discovery_only") is not True:
            errors.append(f"frontier candidate lost discovery-only boundary: {cid}")
        evidence = [x for x in (c.get("evidence") or []) if isinstance(x, dict)]
        if not evidence:
            errors.append(f"frontier candidate without evidence: {cid}")
            continue
        if not any(has_http(x.get("source_url")) for x in evidence):
            errors.append(f"frontier candidate without auditable source URL: {cid}")
        if any(x.get("evidence_grade") != "discovery_only" for x in evidence):
            errors.append(f"frontier evidence grade boundary broken: {cid}")

    # 8) Frontend deploy must not mix asset versions.
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    runtime = (ROOT / "runtime.js").read_text(encoding="utf-8")
    versions = set(re.findall(r"[?&]v=([A-Za-z0-9._-]+)", index))
    runtime_match = re.search(r"ASSET_VERSION\s*=\s*['\"]([^'\"]+)['\"]", runtime)
    if len(versions) != 1:
        errors.append(f"index uses mixed asset versions: {sorted(versions)}")
    if not runtime_match:
        errors.append("runtime ASSET_VERSION not found")
    elif versions and runtime_match.group(1) not in versions:
        errors.append(f"runtime/index asset version mismatch: runtime={runtime_match.group(1)} index={sorted(versions)}")

    # 9) Protect against the exact theme-id regression that caused wrong adjusted scores.
    overview = (ROOT / "overview.js").read_text(encoding="utf-8")
    official = (ROOT / "official-release.js").read_text(encoding="utf-8")
    forbidden = ["contradiction?.[t.theme_id]", "cMap[t.theme_id]", "GUIDE[t.theme_id]"]
    for pattern in forbidden:
        if pattern in overview or pattern in official:
            errors.append(f"unsafe direct theme-id join returned: {pattern}")
    if "const themeId" not in overview:
        errors.append("overview themeId normalizer missing")

    notes.append(f"macro={len(macro.get('observations', []))}")
    notes.append(f"policy={len(policy.get('structural_policies', []))}")
    notes.append(f"themes={len(themes)}")
    notes.append(f"regions={len(regional.get('regions', []))}")
    notes.append(f"entities={len(convergence.get('entities', []))}")
    notes.append(f"frontier={len(frontier.get('attention_queue', []))}")

    if errors:
        print("UI TRUST GATE: FAIL")
        for e in errors:
            print(f"- {e}")
        raise SystemExit(1)
    print("UI TRUST GATE: PASS · " + " · ".join(notes))


if __name__ == "__main__":
    main()
