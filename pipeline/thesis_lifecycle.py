#!/usr/bin/env python3
"""V2.4 Thesis Lifecycle / Delta Intelligence.

Persist one daily theme snapshot plus material intra-day changes, then classify
whether a thesis is strengthening, stable, weakening or approaching reversal.
A minimum of three distinct observation days is required before a directional
lifecycle label is allowed.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
HISTORY_OUT = DATA / "theme_history.json"
OUT = DATA / "thesis_lifecycle.json"

STATUS_RANK = {
    "insufficient": 0,
    "early": 1,
    "developing": 2,
    "converging": 3,
}


def load(name: str, default):
    path = DATA / name
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, type(default)) else default
    except Exception:
        return default


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_dt(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def contradiction_map(payload: dict) -> dict:
    return {x.get("theme_id"): x for x in payload.get("themes", []) if x.get("theme_id")}


def current_theme_state(theme: dict, counter: dict | None) -> dict:
    counter = counter or {}
    supply = theme.get("supply_gap") if isinstance(theme.get("supply_gap"), dict) else {}
    original = int(theme.get("score") or 0)
    adjusted = int(counter.get("tension_adjusted_score") if counter.get("tension_adjusted_score") is not None else original)
    return {
        "theme_id": theme.get("id"),
        "theme_label": theme.get("label"),
        "status": theme.get("status") or "insufficient",
        "score": original,
        "adjusted_score": adjusted,
        "evidence_count": int(theme.get("evidence_count") or 0),
        "family_count": len(theme.get("independent_families") or []),
        "publisher_count": len(theme.get("independent_publishers") or []),
        "counter_signal_count": int(counter.get("counter_signal_count") or 0),
        "tension_level": counter.get("tension_level") or "no_verified_counter_signal",
        "supply_gap_status": supply.get("status") or "unconfirmed_supply_gap",
    }


def state_signature(state: dict) -> tuple:
    return (
        state.get("status"),
        state.get("score"),
        state.get("adjusted_score"),
        state.get("evidence_count"),
        state.get("family_count"),
        state.get("publisher_count"),
        state.get("counter_signal_count"),
        state.get("tension_level"),
        state.get("supply_gap_status"),
    )


def material_change(previous: dict, current: dict) -> bool:
    if not previous:
        return True
    if previous.get("status") != current.get("status"):
        return True
    if previous.get("supply_gap_status") != current.get("supply_gap_status"):
        return True
    if previous.get("tension_level") != current.get("tension_level"):
        return True
    if abs(int(current.get("adjusted_score") or 0) - int(previous.get("adjusted_score") or 0)) >= 3:
        return True
    if abs(int(current.get("family_count") or 0) - int(previous.get("family_count") or 0)) >= 1:
        return True
    if abs(int(current.get("counter_signal_count") or 0) - int(previous.get("counter_signal_count") or 0)) >= 1:
        return True
    return False


def previous_state(snapshots: list[dict], theme_id: str):
    for snap in reversed(snapshots):
        for row in snap.get("themes", []):
            if row.get("theme_id") == theme_id:
                return row, snap.get("captured_at")
    return None, None


def historical_rows(snapshots: list[dict], theme_id: str) -> list[tuple[dict, str]]:
    rows = []
    for snap in snapshots:
        for row in snap.get("themes", []):
            if row.get("theme_id") == theme_id:
                rows.append((row, snap.get("captured_at")))
                break
    return rows


def unique_days(rows: list[tuple[dict, str]]) -> int:
    days = set()
    for _, ts in rows:
        dt = parse_dt(ts)
        if dt:
            days.add(dt.date().isoformat())
    return len(days)


def baseline_delta(rows: list[tuple[dict, str]], current: dict, days: int = 7):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    eligible = []
    for row, ts in rows:
        dt = parse_dt(ts)
        if dt and dt <= cutoff:
            eligible.append((row, dt))
    if not eligible:
        return None
    base = eligible[-1][0]
    return int(current.get("adjusted_score") or 0) - int(base.get("adjusted_score") or 0)


def provisional_direction(previous: dict | None, current: dict) -> tuple[str, int, int, int]:
    if not previous:
        return "new", 0, 0, 0
    score_delta = int(current.get("adjusted_score") or 0) - int(previous.get("adjusted_score") or 0)
    family_delta = int(current.get("family_count") or 0) - int(previous.get("family_count") or 0)
    counter_delta = int(current.get("counter_signal_count") or 0) - int(previous.get("counter_signal_count") or 0)
    status_delta = STATUS_RANK.get(current.get("status"), 0) - STATUS_RANK.get(previous.get("status"), 0)

    if score_delta <= -8 and (counter_delta >= 1 or status_delta < 0):
        direction = "reversal_watch"
    elif score_delta >= 5 or status_delta > 0 or family_delta >= 2:
        direction = "strengthening"
    elif score_delta <= -5 or status_delta < 0 or (counter_delta >= 2 and score_delta < 0):
        direction = "weakening"
    else:
        direction = "stable"
    return direction, score_delta, family_delta, counter_delta


def reason_text(direction: str, score_delta: int, family_delta: int, counter_delta: int) -> str:
    parts = []
    if score_delta:
        parts.append(f"điểm sau phản chứng {score_delta:+d}")
    if family_delta:
        parts.append(f"họ bằng chứng {family_delta:+d}")
    if counter_delta:
        parts.append(f"counter-signal {counter_delta:+d}")
    detail = ", ".join(parts) if parts else "chưa có thay đổi vật chất so với snapshot trước"
    labels = {
        "new": "Thesis mới vào lịch sử",
        "strengthening": "Bằng chứng đang củng cố thesis",
        "stable": "Thesis chưa thay đổi đủ lớn để đổi trạng thái",
        "weakening": "Thesis đang mất độ tin cậy",
        "reversal_watch": "Thesis giảm mạnh và cần theo dõi khả năng đảo trạng thái",
    }
    return f"{labels.get(direction, direction)}: {detail}."


def main() -> None:
    money = load("money_flow_intelligence.json", {})
    contradiction = load("contradiction_intelligence.json", {})
    history = load("theme_history.json", {"version": 1, "snapshots": []})
    snapshots = history.get("snapshots", []) if isinstance(history.get("snapshots"), list) else []
    counters = contradiction_map(contradiction)

    current_states = [
        current_theme_state(theme, counters.get(theme.get("id")))
        for theme in money.get("themes", [])
        if theme.get("id")
    ]

    captured_at = now_iso()
    today = datetime.now(timezone.utc).date().isoformat()
    last_snapshot = snapshots[-1] if snapshots else None
    last_by_id = {x.get("theme_id"): x for x in (last_snapshot or {}).get("themes", [])}
    same_day = False
    if last_snapshot:
        dt = parse_dt(last_snapshot.get("captured_at"))
        same_day = bool(dt and dt.date().isoformat() == today)

    changed = any(material_change(last_by_id.get(x.get("theme_id")), x) for x in current_states)
    should_append = not last_snapshot or not same_day or changed
    if should_append:
        snapshots.append({
            "captured_at": captured_at,
            "source_money_flow_generated_at": money.get("meta", {}).get("generated_at"),
            "source_contradiction_generated_at": contradiction.get("meta", {}).get("generated_at"),
            "themes": current_states,
        })
        snapshots = snapshots[-400:]

    lifecycle_rows = []
    for current in current_states:
        theme_id = current.get("theme_id")
        all_rows = historical_rows(snapshots, theme_id)
        # Compare against the snapshot immediately before the newest one when the newest is current.
        previous = all_rows[-2][0] if len(all_rows) >= 2 and state_signature(all_rows[-1][0]) == state_signature(current) else (all_rows[-1][0] if all_rows else None)
        days_observed = unique_days(all_rows)
        direction, score_delta, family_delta, counter_delta = provisional_direction(previous, current)
        lifecycle_state = direction if days_observed >= 3 else "learning_history"
        confidence = "learning" if days_observed < 3 else ("provisional" if days_observed < 7 else "established")
        counter = counters.get(theme_id, {})
        falsification = counter.get("falsification_conditions") or []
        first_seen = all_rows[0][1] if all_rows else captured_at
        last_changed = all_rows[-1][1] if all_rows else captured_at

        lifecycle_rows.append({
            "theme_id": theme_id,
            "theme_label": current.get("theme_label"),
            "lifecycle_state": lifecycle_state,
            "provisional_direction": direction,
            "history_confidence": confidence,
            "observation_days": days_observed,
            "snapshot_count": len(all_rows),
            "first_seen_at": first_seen,
            "last_snapshot_at": last_changed,
            "current_status": current.get("status"),
            "current_score": current.get("score"),
            "current_adjusted_score": current.get("adjusted_score"),
            "delta_vs_previous": score_delta if previous else None,
            "family_delta_vs_previous": family_delta if previous else None,
            "counter_signal_delta_vs_previous": counter_delta if previous else None,
            "delta_vs_7d": baseline_delta(all_rows, current, 7),
            "supply_gap_status": current.get("supply_gap_status"),
            "tension_level": current.get("tension_level"),
            "reason": reason_text(direction, score_delta, family_delta, counter_delta),
            "upgrade_conditions": [
                "thêm họ bằng chứng độc lập và publisher độc lập",
                "demand phải chuyển thành buyer/economics quan sát được",
                "supply-side phải cho thấy capacity pressure hoặc gap có thể kiểm chứng",
            ],
            "downgrade_conditions": falsification,
        })

    order = {"reversal_watch": 0, "weakening": 1, "strengthening": 2, "stable": 3, "learning_history": 4}
    lifecycle_rows.sort(key=lambda x: (order.get(x.get("lifecycle_state"), 9), -(x.get("current_adjusted_score") or 0)))
    observed_days = max([x.get("observation_days", 0) for x in lifecycle_rows], default=0)
    active_directional = observed_days >= 3
    if not active_directional:
        thesis = f"Lifecycle đang học lịch sử: mới có {observed_days}/3 ngày quan sát tối thiểu. Hướng tăng/giảm hiện chỉ là provisional, chưa được gọi là trend."
    else:
        strengthening = [x for x in lifecycle_rows if x.get("lifecycle_state") == "strengthening"]
        weakening = [x for x in lifecycle_rows if x.get("lifecycle_state") in {"weakening", "reversal_watch"}]
        if strengthening or weakening:
            up = ", ".join(x.get("theme_label") for x in strengthening[:3]) or "không có"
            down = ", ".join(x.get("theme_label") for x in weakening[:3]) or "không có"
            thesis = f"Lifecycle active — đang mạnh lên: {up}; đang yếu đi/reversal watch: {down}."
        else:
            thesis = "Lifecycle active nhưng chưa có theme thay đổi vật chất so với baseline gần nhất."

    history_payload = {
        "version": 1,
        "updated_at": captured_at,
        "retention_rule": "one_daily_snapshot_plus_material_intraday_changes_last_400_snapshots",
        "snapshots": snapshots,
    }
    HISTORY_OUT.write_text(json.dumps(history_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    payload = {
        "meta": {
            "version": "2.4.0",
            "generated_at": captured_at,
            "mode": "thesis_lifecycle_and_delta_intelligence",
            "status": "active" if active_directional else "learning_history",
            "principle": "do_not_call_directional_trend_before_three_distinct_observation_days",
        },
        "thesis": thesis,
        "coverage": {
            "themes": len(lifecycle_rows),
            "history_snapshots": len(snapshots),
            "max_observation_days": observed_days,
            "directional_lifecycle_active": active_directional,
            "strengthening": sum(1 for x in lifecycle_rows if x.get("lifecycle_state") == "strengthening"),
            "weakening": sum(1 for x in lifecycle_rows if x.get("lifecycle_state") == "weakening"),
            "reversal_watch": sum(1 for x in lifecycle_rows if x.get("lifecycle_state") == "reversal_watch"),
        },
        "themes": lifecycle_rows,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"thesis-lifecycle themes={len(lifecycle_rows)} days={observed_days} active={active_directional}")


if __name__ == "__main__":
    main()
