#!/usr/bin/env python3
"""Rebase comparable history when intelligence methodology changes.

A scoring/taxonomy change must never be interpreted as an economic delta. This stage
keeps a small audit record of the previous history size, then starts fresh comparable
Theme/Report histories exactly once for each methodology version.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STATE = DATA / "methodology_state.json"
THEME = DATA / "theme_history.json"
REPORT = DATA / "report_history.json"
VERSION = "3.0.1-trust-semantics-v1"


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def save(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    now = datetime.now(timezone.utc).isoformat()
    state = load(STATE, {})
    if state.get("methodology_version") == VERSION:
        print(f"trust-rebase unchanged methodology={VERSION}")
        return

    theme = load(THEME, {"version": 1, "snapshots": []})
    reports = load(REPORT, [])
    old_theme_count = len(theme.get("snapshots", [])) if isinstance(theme, dict) else 0
    old_report_count = len(reports) if isinstance(reports, list) else 0
    prior_version = state.get("methodology_version")

    save(THEME, {
        "version": 1,
        "updated_at": now,
        "retention_rule": "comparable_snapshots_only_after_current_methodology_rebase",
        "rebase_reason": "scoring_or_evidence_semantics_changed; old scores are not comparable",
        "snapshots": [],
    })
    save(REPORT, [])
    save(STATE, {
        "methodology_version": VERSION,
        "rebased_at": now,
        "previous_methodology_version": prior_version,
        "legacy_history_summary": {
            "theme_snapshots_excluded_from_comparison": old_theme_count,
            "report_snapshots_excluded_from_comparison": old_report_count,
        },
        "principle": "methodology_change_is_not_economic_change",
    })
    print(f"trust-rebase {prior_version or 'none'} -> {VERSION}; excluded theme={old_theme_count} reports={old_report_count}")


if __name__ == "__main__":
    main()
