#!/usr/bin/env python3
"""Periodic Intelligence Reports for Opportunity Intelligence OS V3.

This is an output layer, not a new prediction engine. It only summarizes normalized
intelligence already produced by upstream modules and keeps period snapshots so the
system can compare what it believed across days, weeks and months.
"""
from __future__ import annotations

import calendar
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "intelligence_reports.json"
HISTORY = DATA / "report_history.json"
VN = ZoneInfo("Asia/Ho_Chi_Minh")
VERSION = "3.0.0"


def load(name: str, fallback=None):
    path = DATA / name
    if fallback is None:
        fallback = {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value
    except Exception:
        return fallback


def now_local() -> datetime:
    return datetime.now(timezone.utc).astimezone(VN)


def num(value, default=0):
    try:
        return float(value)
    except Exception:
        return default


def short(text, limit=260):
    value = " ".join(str(text or "").split())
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def unique(items):
    out = []
    seen = set()
    for item in items:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, (dict, list)) else str(item)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def period_keys(dt: datetime):
    iso = dt.isocalendar()
    return {
        "daily": dt.strftime("%Y-%m-%d"),
        "weekly": f"{iso.year}-W{iso.week:02d}",
        "monthly": dt.strftime("%Y-%m"),
    }


def period_state(kind: str, dt: datetime):
    if kind == "daily":
        return "live_today"
    if kind == "weekly":
        return "final" if dt.weekday() == 6 else "week_to_date"
    last_day = calendar.monthrange(dt.year, dt.month)[1]
    return "final" if dt.day == last_day else "month_to_date"


def report_label(kind: str):
    return {
        "daily": "Daily Intelligence Brief",
        "weekly": "Weekly Intelligence Report",
        "monthly": "Monthly Regime Review",
    }[kind]


def build_snapshot(bundle: dict):
    lifecycle = bundle["lifecycle"]
    coverage = bundle["coverage"]
    convergence = bundle["convergence"]
    regional = bundle["regional"]

    themes = {}
    for t in lifecycle.get("themes", []):
        tid = t.get("theme_id")
        if not tid:
            continue
        themes[tid] = {
            "label": t.get("theme_label") or tid,
            "score": t.get("current_adjusted_score", t.get("current_score")),
            "state": t.get("lifecycle_state"),
            "direction": t.get("provisional_direction"),
            "observation_days": t.get("observation_days", 0),
        }

    entities = {}
    for e in convergence.get("entities", []):
        label = e.get("label")
        if label:
            entities[label] = {
                "score": e.get("convergence_score", 0),
                "status": e.get("status"),
                "primary": e.get("primary_evidence_count", 0),
                "media": e.get("media_evidence_count", 0),
            }

    regions = {}
    for r in regional.get("regions", []):
        name = r.get("region")
        if name:
            regions[name] = {
                "state": r.get("state"),
                "score": r.get("score", 0),
                "iip": r.get("iip_7m_yoy_pct"),
                "fdi": r.get("fdi_yoy_pct"),
            }

    cov = coverage.get("coverage", {})
    return {
        "themes": themes,
        "entities": entities,
        "regions": regions,
        "coverage": {
            "strong": cov.get("strong", 0),
            "partial": cov.get("partial", 0),
            "weak": cov.get("weak", 0),
            "broken": cov.get("broken", 0),
            "missing": cov.get("missing", 0),
            "productive_sources": cov.get("productive_sources", 0),
            "source_errors": cov.get("source_errors", 0),
        },
    }


def previous_for(history: list, kind: str, period_key: str):
    rows = [x for x in history if x.get("kind") == kind and x.get("period_key") != period_key]
    return rows[-1] if rows else None


def snapshot_delta(current: dict, previous: dict | None):
    if not previous:
        return {
            "available": False,
            "theme_changes": [],
            "new_entities": [],
            "coverage_change": None,
        }
    old = previous.get("snapshot", {})
    changes = []
    old_themes = old.get("themes", {})
    for tid, cur in current.get("themes", {}).items():
        prev = old_themes.get(tid)
        if not prev:
            changes.append({"theme_id": tid, "label": cur.get("label"), "delta": None, "change": "new_theme"})
            continue
        if cur.get("score") is None or prev.get("score") is None:
            continue
        delta = round(num(cur.get("score")) - num(prev.get("score")), 1)
        if abs(delta) >= 3:
            changes.append({"theme_id": tid, "label": cur.get("label"), "delta": delta, "change": "strengthened" if delta > 0 else "weakened"})
    changes.sort(key=lambda x: abs(x.get("delta") or 999), reverse=True)

    old_entities = set(old.get("entities", {}).keys())
    new_entities = [x for x in current.get("entities", {}).keys() if x not in old_entities]

    c = current.get("coverage", {})
    p = old.get("coverage", {})
    coverage_change = {
        "strong": num(c.get("strong")) - num(p.get("strong")),
        "productive_sources": num(c.get("productive_sources")) - num(p.get("productive_sources")),
        "source_errors": num(c.get("source_errors")) - num(p.get("source_errors")),
    }
    return {
        "available": True,
        "theme_changes": changes[:8],
        "new_entities": new_entities[:8],
        "coverage_change": coverage_change,
    }


def lifecycle_readiness(bundle: dict, kind: str):
    life_cov = bundle["lifecycle"].get("coverage", {})
    days = int(life_cov.get("max_observation_days") or 0)
    need = {"daily": 2, "weekly": 7, "monthly": 21}[kind]
    return {
        "observation_days": days,
        "recommended_days": need,
        "history_ready": days >= need,
    }


def strongest_themes(bundle: dict, limit=4):
    rows = bundle["lifecycle"].get("themes", [])
    rows = sorted(rows, key=lambda x: num(x.get("current_adjusted_score", x.get("current_score"))), reverse=True)
    return rows[:limit]


def executive_summary(bundle: dict, delta: dict, kind: str, readiness: dict):
    themes = strongest_themes(bundle, 3)
    entities = sorted(bundle["convergence"].get("entities", []), key=lambda x: num(x.get("convergence_score")), reverse=True)
    regions = [r for r in bundle["regional"].get("regions", []) if r.get("state") == "dual_acceleration"]
    parts = []

    if delta.get("available") and delta.get("theme_changes"):
        top = delta["theme_changes"][0]
        sign = "+" if num(top.get("delta")) > 0 else ""
        parts.append(f"Thay đổi lớn nhất so với kỳ trước nằm ở {top.get('label')}: {sign}{top.get('delta')} điểm.")
    elif themes:
        names = ", ".join(t.get("theme_label", t.get("theme_id", "")) for t in themes[:2])
        parts.append(f"Các theme có điểm sau phản chứng cao nhất hiện là {names}.")

    if entities:
        e = entities[0]
        parts.append(f"Entity nổi bật nhất trong Convergence Radar hiện là {e.get('label')} ở trạng thái {e.get('status', 'watch')}.")
    if regions:
        parts.append(f"Regional divergence đang đáng chú ý tại {regions[0].get('region')}, nơi vốn mới và sản xuất cùng tăng theo dữ liệu quan sát.")

    cov = bundle["coverage"].get("coverage", {})
    parts.append(f"Độ phủ nguồn hiện có {cov.get('strong', 0)} domain STRONG, {cov.get('weak', 0)} WEAK, {cov.get('broken', 0)} BROKEN và {cov.get('missing', 0)} MISSING.")

    if not readiness["history_ready"]:
        parts.append(f"Lịch sử mới có {readiness['observation_days']}/{readiness['recommended_days']} ngày khuyến nghị cho {report_label(kind)}; mọi kết luận về hướng dài hơn vẫn là provisional.")
    return parts


def what_changed(bundle: dict, delta: dict, kind: str):
    out = []
    if delta.get("available"):
        for x in delta.get("theme_changes", [])[:5]:
            if x.get("delta") is None:
                out.append({"type": "theme", "title": x.get("label"), "assessment": "Theme mới xuất hiện trong snapshot kỳ này."})
            else:
                direction = "mạnh lên" if num(x.get("delta")) > 0 else "yếu đi"
                out.append({"type": "theme", "title": x.get("label"), "assessment": f"{direction} {abs(num(x.get('delta'))):g} điểm so với kỳ trước."})
        for label in delta.get("new_entities", [])[:3]:
            out.append({"type": "entity", "title": label, "assessment": "Entity mới xuất hiện trong convergence snapshot so với kỳ trước."})
    if not out:
        for t in strongest_themes(bundle, 4):
            d = t.get("delta_vs_previous")
            reason = t.get("reason") or "Chưa có thay đổi vật chất được xác nhận."
            out.append({
                "type": "theme",
                "title": t.get("theme_label") or t.get("theme_id"),
                "assessment": short(f"Delta snapshot gần nhất {d:+g}. {reason}" if isinstance(d, (int, float)) else reason),
            })
    return out[:6]


def entity_watch(bundle: dict):
    out = []
    entities = sorted(bundle["convergence"].get("entities", []), key=lambda x: num(x.get("convergence_score")), reverse=True)
    for e in entities[:5]:
        if e.get("status") == "not_observed":
            continue
        out.append({
            "label": e.get("label"),
            "status": e.get("status"),
            "score": e.get("convergence_score"),
            "why": short(e.get("why_now")),
            "primary_evidence": e.get("primary_evidence_count", 0),
            "media_evidence": e.get("media_evidence_count", 0),
            "question": (e.get("investigation_questions") or ["Driver kinh tế nào đang thay đổi quanh entity này?"])[0],
        })
    return out


def regional_watch(bundle: dict):
    out = []
    priority = {"dual_acceleration": 3, "production_strong_capital_cooling": 2, "capital_acceleration_production_lag": 2}
    rows = sorted(bundle["regional"].get("regions", []), key=lambda x: (priority.get(x.get("state"), 0), num(x.get("score"))), reverse=True)
    for r in rows[:5]:
        out.append({
            "region": r.get("region"),
            "state": r.get("state"),
            "interpretation": short(r.get("interpretation")),
            "iip_yoy": r.get("iip_7m_yoy_pct"),
            "fdi_yoy": r.get("fdi_yoy_pct"),
            "next_proxy": (r.get("next_proxies") or [None])[0],
        })
    return out


def contradictions(bundle: dict):
    rows = []
    for t in bundle["contradiction"].get("themes", []):
        counters = t.get("counter_signals") or t.get("verified_counter_signals") or []
        if not counters and t.get("tension_level") in (None, "no_verified_counter_signal"):
            continue
        rows.append({
            "theme": t.get("theme_label") or t.get("theme_id"),
            "tension": t.get("tension_level"),
            "adjusted_score": t.get("tension_adjusted_score"),
            "counter_signals": [short(x.get("text") if isinstance(x, dict) else x) for x in counters[:3]],
            "reading": short(t.get("reading_rule") or t.get("interpretation")),
        })
    return rows[:5]


def blind_spots(bundle: dict):
    out = []
    for x in bundle["coverage"].get("critical_blind_spots", [])[:8]:
        out.append({
            "domain": x.get("label") or x.get("domain_id"),
            "status": x.get("status"),
            "why": short(x.get("why")),
            "coverage_note": short(x.get("coverage_note")),
            "planned_next_sources": x.get("planned_next_sources") or [],
        })
    return out


def investigation_queue(bundle: dict):
    questions = []
    for e in entity_watch(bundle)[:2]:
        questions.append({"priority": "entity", "subject": e.get("label"), "question": e.get("question")})
    for t in strongest_themes(bundle, 3):
        upgrades = t.get("upgrade_conditions") or []
        if upgrades:
            questions.append({"priority": "theme", "subject": t.get("theme_label"), "question": upgrades[0]})
        downs = t.get("downgrade_conditions") or []
        if downs:
            questions.append({"priority": "falsification", "subject": t.get("theme_label"), "question": downs[0]})
    for b in blind_spots(bundle)[:2]:
        questions.append({"priority": "coverage", "subject": b.get("domain"), "question": f"Bổ sung bằng chứng nào để giảm blind spot: {b.get('coverage_note')}"})
    return unique(questions)[:7]


def build_report(kind: str, dt: datetime, bundle: dict, history: list, snapshot: dict):
    keys = period_keys(dt)
    key = keys[kind]
    prev = previous_for(history, kind, key)
    delta = snapshot_delta(snapshot, prev)
    readiness = lifecycle_readiness(bundle, kind)
    history_status = "ready" if readiness["history_ready"] else "learning_history"
    return {
        "kind": kind,
        "period_key": key,
        "period_state": period_state(kind, dt),
        "title": report_label(kind),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "local_generated_at": dt.isoformat(),
        "history_status": history_status,
        "history_readiness": readiness,
        "executive_summary": executive_summary(bundle, delta, kind, readiness),
        "what_changed": what_changed(bundle, delta, kind),
        "entity_watch": entity_watch(bundle),
        "regional_watch": regional_watch(bundle),
        "contradictions": contradictions(bundle),
        "blind_spots": blind_spots(bundle),
        "investigation_queue": investigation_queue(bundle),
        "period_delta": delta,
        "snapshot": snapshot,
        "reading_rule": "Report chỉ tổng hợp intelligence đã chuẩn hóa. Nó không biến inference thành fact, không tạo BUY/SELL và không được tăng confidence khi history/source coverage chưa đủ.",
    }


def upsert_history(history: list, report: dict):
    key = (report.get("kind"), report.get("period_key"))
    replaced = False
    for i, row in enumerate(history):
        if (row.get("kind"), row.get("period_key")) == key:
            history[i] = report
            replaced = True
            break
    if not replaced:
        history.append(report)
    history.sort(key=lambda x: (x.get("period_key", ""), x.get("kind", "")))
    return history[-420:]


def main():
    dt = now_local()
    bundle = {
        "lifecycle": load("thesis_lifecycle.json"),
        "coverage": load("source_coverage_intelligence.json"),
        "convergence": load("entity_convergence_intelligence.json"),
        "regional": load("regional_intelligence.json"),
        "contradiction": load("contradiction_intelligence.json"),
        "policy": load("policy_intelligence.json"),
        "money": load("money_flow_intelligence.json"),
        "corporate": load("corporate_intelligence.json"),
        "macro": load("macro_observations.json"),
    }
    raw_history = load("report_history.json", [])
    history = raw_history if isinstance(raw_history, list) else []
    snapshot = build_snapshot(bundle)

    reports = {}
    for kind in ("daily", "weekly", "monthly"):
        report = build_report(kind, dt, bundle, history, snapshot)
        reports[kind] = report
        history = upsert_history(history, report)

    OUT.write_text(json.dumps({
        "meta": {
            "version": VERSION,
            "mode": "periodic_intelligence_reporting_output_layer",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "local_date": dt.strftime("%Y-%m-%d"),
            "principle": "history_delta_plus_falsification_not_news_summary",
        },
        "reports": reports,
        "history_count": len(history),
        "reporting_rule": "Daily = material delta; Weekly = main intelligence review; Monthly = regime/thesis audit. Insufficient history must remain explicit.",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    HISTORY.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"reports daily={reports['daily']['period_key']} weekly={reports['weekly']['period_key']} monthly={reports['monthly']['period_key']} history={len(history)}")


if __name__ == "__main__":
    main()
