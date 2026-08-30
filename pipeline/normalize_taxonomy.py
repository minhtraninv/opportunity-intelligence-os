#!/usr/bin/env python3
"""Reclassify stored procurement history with the canonical taxonomy.

Collectors are intentionally allowed to stay simple. This stage repairs historical
categories after taxonomy changes, then rebuilds Buyer and Partner intelligence so an
old classification mistake does not remain embedded in future decisions.
"""
from __future__ import annotations

import json
from datetime import timezone
from pathlib import Path

import action_intel as ai
import partner_intel as pi
import taxonomy

ROOT = Path(__file__).resolve().parents[1]
ACTION_HISTORY = ROOT / "data" / "action_history.json"
ACTION_OUTPUT = ROOT / "data" / "action_intelligence.json"
PARTNER_HISTORY = ROOT / "data" / "partner_history.json"
PARTNER_OUTPUT = ROOT / "data" / "partner_intelligence.json"


def load(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def errors_from_health(health):
    return [x.get("error") for x in health or [] if x.get("status") == "error" and x.get("error")]


def normalize_history(history: dict, title_field: str):
    changed = 0
    for item in history.get("items", []):
        title = item.get(title_field) or ""
        category = taxonomy.classify(title)
        tags = taxonomy.matched_categories(title)
        if item.get("procurement_category") != category or item.get("procurement_tags") != tags:
            item["procurement_category"] = category
            item["procurement_tags"] = tags
            changed += 1
    return changed


def main():
    captured = ai.now_utc().astimezone(timezone.utc)

    action_history = load(ACTION_HISTORY, {"version": 3, "items": []})
    partner_history = load(PARTNER_HISTORY, {"version": 1, "items": []})
    action_changed = normalize_history(action_history, "title")
    partner_changed = normalize_history(partner_history, "tender_title")
    write(ACTION_HISTORY, action_history)
    write(PARTNER_HISTORY, partner_history)

    previous_action = load(ACTION_OUTPUT, {})
    action_health = previous_action.get("source_health", [])
    action_errors = errors_from_health(action_health)
    action_output = ai.build_output(action_history, captured, action_errors, action_health)
    action_output.setdefault("meta", {})["taxonomy_normalized"] = True
    action_output["meta"]["taxonomy_version"] = "1.4.0"
    write(ACTION_OUTPUT, action_output)

    previous_partner = load(PARTNER_OUTPUT, {})
    partner_health = previous_partner.get("source_health", [])
    partner_errors = errors_from_health(partner_health)
    details_fetched = previous_partner.get("coverage", {}).get("result_details_fetched_last_run", 0)
    partner_output = pi.build_output(partner_history, captured, partner_errors, partner_health, details_fetched)
    partner_output.setdefault("meta", {})["taxonomy_normalized"] = True
    partner_output["meta"]["taxonomy_version"] = "1.4.0"
    write(PARTNER_OUTPUT, partner_output)

    print(
        f"taxonomy-normalized action_changed={action_changed} partner_changed={partner_changed} "
        f"action_items={len(action_history.get('items', []))} partner_events={len(partner_history.get('items', []))}"
    )


if __name__ == "__main__":
    main()
