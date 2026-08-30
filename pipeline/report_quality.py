#!/usr/bin/env python3
"""Quality gate for periodic intelligence reports.

Keeps report prose tied to the actual Contradiction Engine schema. Readable current
counter-signals are required when the contradiction snapshot is current; a snapshot
that was explicitly aged out is a valid empty state, not a pipeline failure.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS = DATA / "intelligence_reports.json"
HISTORY = DATA / "report_history.json"
CONTRADICTION = DATA / "contradiction_intelligence.json"


def load(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def save(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def normalized_contradictions(source: dict):
    out = []
    for theme in source.get("themes", []):
        signals = theme.get("counter_signals") or []
        if not signals:
            continue
        rows = []
        falsifiers = []
        for signal in signals[:3]:
            if not isinstance(signal, dict):
                if str(signal).strip():
                    rows.append(str(signal).strip())
                continue
            title = " ".join(str(signal.get("title") or "").split())
            interpretation = " ".join(str(signal.get("interpretation") or "").split())
            falsifies = " ".join(str(signal.get("falsifies_if") or "").split())
            if title and interpretation:
                rows.append(f"{title} — {interpretation}")
            elif title:
                rows.append(title)
            elif interpretation:
                rows.append(interpretation)
            if falsifies:
                falsifiers.append(falsifies)
        if not rows:
            continue
        out.append({
            "theme": theme.get("theme_label") or theme.get("theme_id"),
            "tension": theme.get("tension_level"),
            "adjusted_score": theme.get("tension_adjusted_score"),
            "counter_signals": rows,
            "reading": falsifiers[0] if falsifiers else theme.get("rule") or "Phải đọc thesis cùng counter-evidence.",
        })
    return out[:5]


def main():
    reports = load(REPORTS, {})
    history = load(HISTORY, [])
    source = load(CONTRADICTION, {})
    freshness = str((source.get("meta") or {}).get("freshness_status") or "unknown")
    fixed = normalized_contradictions(source)

    if not fixed and freshness != "stale":
        raise RuntimeError(
            f"Report quality gate: Contradiction Engine has no readable current counter-signals (freshness={freshness})"
        )

    current_keys = set()
    for report in (reports.get("reports") or {}).values():
        if not isinstance(report, dict):
            continue
        report["contradictions"] = fixed
        if freshness == "stale":
            report["counter_signal_notice"] = (
                "Counter-signal snapshot đã stale và được chủ động loại khỏi current report; "
                "dữ liệu cũ chỉ còn là historical context."
            )
        current_keys.add((report.get("kind"), report.get("period_key")))

    if isinstance(history, list):
        for report in history:
            if not isinstance(report, dict):
                continue
            if (report.get("kind"), report.get("period_key")) in current_keys:
                report["contradictions"] = fixed
                if freshness == "stale":
                    report["counter_signal_notice"] = (
                        "Counter-signal snapshot đã stale và được chủ động loại khỏi current report."
                    )

    reports.setdefault("meta", {})["quality_gate"] = (
        "stale_falsification_snapshot_suppressed" if freshness == "stale"
        else "falsification_evidence_readable"
    )
    save(REPORTS, reports)
    save(HISTORY, history)
    print(
        f"report-quality contradictions={len(fixed)} freshness={freshness} current_periods={len(current_keys)}"
    )


if __name__ == "__main__":
    main()
