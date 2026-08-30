#!/usr/bin/env python3
"""Measure freshness of manually verified structural snapshots.

Verified does not mean current forever. This state is consumed by trust_money,
trust_staleness and the frontend so old snapshots lose the right to pose as current.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "freshness_state.json"

SPECS = {
    "macro": ("macro_observations.json", 45, 60),
    "regional": ("regional_observations.json", 45, 60),
    "contradiction": ("contradiction_observations.json", 45, 60),
}


def load(name: str):
    try:
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    except Exception:
        return {}


def parse(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def main() -> None:
    now = datetime.now(timezone.utc)
    datasets = {}
    for key, (filename, fresh_days, stale_days) in SPECS.items():
        payload = load(filename)
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        updated = parse(meta.get("updated_at") or meta.get("generated_at"))
        if updated is None:
            age = None
            status = "unknown"
        else:
            age = max(0, int((now - updated).total_seconds() // 86400))
            status = "fresh" if age <= fresh_days else "aging" if age <= stale_days else "stale"
        datasets[key] = {
            "file": filename,
            "updated_at": updated.isoformat() if updated else None,
            "age_days": age,
            "status": status,
            "fresh_through_days": fresh_days,
            "stale_after_days": stale_days,
            "observation_count": len(payload.get("observations", [])) if isinstance(payload.get("observations"), list) else None,
        }

    OUT.write_text(json.dumps({
        "meta": {"version": "3.0.1", "generated_at": now.isoformat(), "mode": "verified_snapshot_freshness"},
        "datasets": datasets,
        "principle": "verified_snapshot_can_age_out_of_current_intelligence",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("trust-freshness " + " ".join(f"{k}={v['status']}:{v['age_days']}d" for k,v in datasets.items()))


if __name__ == "__main__":
    main()
