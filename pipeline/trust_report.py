#!/usr/bin/env python3
"""Apply maturity gates to periodic reports.

Daily may be a clearly labeled current-state brief while history is young. Weekly and
Monthly are locked until their own history threshold is met; the system must not fill
the absence of history with confident-looking prose.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS = DATA / "intelligence_reports.json"
HISTORY = DATA / "report_history.json"


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def save(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def harden(report: dict) -> dict:
    kind = report.get("kind")
    readiness = report.get("history_readiness") or {}
    ready = bool(readiness.get("history_ready"))
    days = int(readiness.get("observation_days") or 0)
    need = int(readiness.get("recommended_days") or 0)

    if ready:
        report["analysis_status"] = "history_ready"
        report["trust_notice"] = "Kỳ báo cáo đã vượt ngưỡng lịch sử tối thiểu; vẫn phải đọc cùng blind spots và phản chứng."
        return report

    if kind == "daily":
        report["analysis_status"] = "current_state_only"
        report["trust_notice"] = (
            f"Mới có {days}/{need} ngày lịch sử khuyến nghị. Daily hiện là current-state brief, "
            "không phải kết luận xu hướng theo thời gian."
        )
        # Do not let intra-day/methodology deltas masquerade as daily economic change.
        report["what_changed"] = []
        report["period_delta"] = {"available": False, "current_state_only": True, "reason": "insufficient_comparable_daily_history"}
        return report

    report["analysis_status"] = "locked_learning_history"
    report["trust_notice"] = (
        f"{kind.capitalize()} cần tối thiểu {need} ngày lịch sử; hiện mới có {days}. "
        "Hệ thống chủ động không tạo phân tích kỳ để tránh pseudo-trend."
    )
    report["executive_summary"] = [report["trust_notice"], "Trong thời gian chờ, dùng Daily để đọc trạng thái hiện tại và Source Coverage để biết các blind spot."]
    report["what_changed"] = []
    report["entity_watch"] = []
    report["regional_watch"] = []
    report["contradictions"] = []
    report["investigation_queue"] = []
    report["period_delta"] = {"available": False, "locked": True, "reason": "insufficient_history"}
    return report


def main() -> None:
    payload = load(REPORTS, {})
    history = load(HISTORY, [])
    current_keys = set()
    for report in (payload.get("reports") or {}).values():
        if isinstance(report, dict):
            harden(report)
            current_keys.add((report.get("kind"), report.get("period_key")))

    if isinstance(history, list):
        for report in history:
            if isinstance(report, dict) and (report.get("kind"), report.get("period_key")) in current_keys:
                harden(report)

    meta = payload.setdefault("meta", {})
    meta["trust_patch"] = "3.0.1"
    meta["trust_hardened_at"] = datetime.now(timezone.utc).isoformat()
    meta["principle"] = "current_state_is_not_period_trend_and_insufficient_history_must_lock_period_analysis"
    save(REPORTS, payload)
    save(HISTORY, history)
    statuses = {k: v.get("analysis_status") for k, v in (payload.get("reports") or {}).items() if isinstance(v, dict)}
    print(f"trust-report {statuses}")


if __name__ == "__main__":
    main()
