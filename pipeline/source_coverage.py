#!/usr/bin/env python3
"""Audit whether Opportunity Intelligence OS can actually see the economy it claims to read."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REGISTRY = DATA / "source_registry.json"
OUTPUT = DATA / "source_coverage_intelligence.json"


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def main_health(source: dict, raw: dict, counts: Counter) -> dict:
    name = str(source.get("name") or "")
    errors = raw.get("errors") or []
    matched_error = next((str(x) for x in errors if name and name in str(x)), None)
    if matched_error:
        return {"status": "error", "items_this_run": 0, "error": matched_error}
    return {"status": "ok", "items_this_run": counts.get(source.get("id"), 0), "error": None}


def build_source_health(registry: dict) -> list[dict]:
    raw = load(DATA / "raw_feed.json", {})
    media = load(DATA / "entity_media_intelligence.json", {})
    corporate = load(DATA / "corporate_intelligence.json", {})
    procurement = load(DATA / "action_intelligence.json", {})

    raw_counts = Counter(x.get("source_id") for x in raw.get("items", []) if isinstance(x, dict))
    media_health = {x.get("source_id"): x for x in media.get("source_health", []) if isinstance(x, dict)}
    corp_health = {x.get("source_id"): x for x in corporate.get("source_health", []) if isinstance(x, dict)}

    rows = []
    for source in registry.get("sources", []):
        collector = source.get("collector")
        if collector == "planned":
            health = {"status": "planned", "items_this_run": 0, "error": None}
        elif collector == "main":
            health = main_health(source, raw, raw_counts)
        elif collector == "entity_media":
            row = media_health.get(source.get("id"), {})
            health = {
                "status": row.get("status") or "unknown",
                "items_this_run": int(row.get("items_this_run") or 0),
                "error": row.get("error"),
            }
        elif collector == "corporate":
            row = corp_health.get(source.get("id"), {})
            health = {
                "status": row.get("status") or "unknown",
                "items_this_run": int(row.get("items_this_run") or 0),
                "error": row.get("error"),
            }
        elif collector == "procurement":
            errors = int(procurement.get("coverage", {}).get("source_errors_last_run") or 0)
            health = {
                "status": "error" if errors else "ok",
                "items_this_run": int(procurement.get("coverage", {}).get("active_recent_tenders") or 0),
                "error": f"{errors} procurement source errors" if errors else None,
            }
        else:
            health = {"status": "unknown", "items_this_run": 0, "error": None}

        rows.append({
            **source,
            "health": health.get("status"),
            "items_this_run": health.get("items_this_run", 0),
            "error": health.get("error"),
        })
    return rows


def domain_status(domain: dict, sources: list[dict]) -> dict:
    relevant = [x for x in sources if domain.get("id") in (x.get("domains") or [])]
    active = [x for x in relevant if x.get("status") != "planned"]
    planned = [x for x in relevant if x.get("status") == "planned"]
    healthy = [x for x in active if x.get("health") == "ok"]
    broken = [x for x in active if x.get("health") == "error"]
    evidence = sum(int(x.get("items_this_run") or 0) for x in healthy)
    target = int(domain.get("target_healthy_sources") or 1)

    if not active:
        status = "missing"
    elif not healthy and broken:
        status = "broken"
    elif len(healthy) >= target and evidence > 0:
        status = "strong"
    elif healthy and evidence > 0:
        status = "partial"
    else:
        status = "weak"

    next_sources = [x.get("name") for x in planned[:3]]
    if status == "strong":
        note = "Độ phủ hiện tại đủ dùng cho discovery; vẫn cần theo dõi freshness và độc lập nguồn."
    elif status == "partial":
        note = "Đã nhìn thấy tín hiệu thật nhưng chưa đủ đa nguồn để yên tâm về độ phủ."
    elif status == "weak":
        note = "Có collector/nguồn nhưng lần chạy hiện tại chưa tạo đủ evidence; dễ bỏ sót thay đổi quan trọng."
    elif status == "broken":
        note = "Nguồn đang lỗi và chưa có nguồn khỏe thay thế trong domain này."
    else:
        note = "Domain chưa có collector active; đây là blind spot thực sự."

    return {
        **domain,
        "status": status,
        "active_sources": len(active),
        "healthy_sources": len(healthy),
        "broken_sources": len(broken),
        "evidence_items_this_run": evidence,
        "healthy_source_names": [x.get("name") for x in healthy],
        "broken_source_names": [x.get("name") for x in broken],
        "planned_next_sources": next_sources,
        "coverage_note": note,
    }


def main() -> None:
    now = datetime.now(timezone.utc)
    registry = load(REGISTRY, {"sources": [], "domains": []})
    sources = build_source_health(registry)
    domains = [domain_status(x, sources) for x in registry.get("domains", []) if isinstance(x, dict)]

    severity = {"missing": 5, "broken": 4, "weak": 3, "partial": 2, "strong": 1}
    domains.sort(key=lambda x: (int(x.get("priority") or 9), -severity.get(x.get("status"), 0), x.get("label") or ""))
    blind = [x for x in domains if x.get("status") != "strong"]
    blind.sort(key=lambda x: (int(x.get("priority") or 9), -severity.get(x.get("status"), 0)))

    counts = Counter(x.get("status") for x in domains)
    source_counts = Counter(x.get("health") for x in sources)
    primary_active = [x for x in sources if x.get("type") not in {"media_discovery", "behavioral"} and x.get("status") != "planned"]

    payload = {
        "meta": {
            "version": "2.8.0",
            "generated_at": now.isoformat(),
            "mode": "source_coverage_and_blind_spot_audit",
            "principle": "intelligence_quality_is_bounded_by_what_the_system_can_observe",
        },
        "thesis": (
            "Không tăng độ tự tin của intelligence nếu độ phủ nguồn chưa tăng tương ứng. "
            "Nguồn primary dùng để xác minh; media dùng để discovery; một domain thiếu nguồn phải được hiển thị như blind spot."
        ),
        "coverage": {
            "domains": len(domains),
            "strong": counts.get("strong", 0),
            "partial": counts.get("partial", 0),
            "weak": counts.get("weak", 0),
            "broken": counts.get("broken", 0),
            "missing": counts.get("missing", 0),
            "registered_sources": len(sources),
            "active_primary_sources": len(primary_active),
            "healthy_sources": source_counts.get("ok", 0),
            "source_errors": source_counts.get("error", 0),
            "planned_sources": source_counts.get("planned", 0),
        },
        "critical_blind_spots": [
            {
                "domain_id": x.get("id"),
                "label": x.get("label"),
                "status": x.get("status"),
                "priority": x.get("priority"),
                "why": x.get("why"),
                "coverage_note": x.get("coverage_note"),
                "planned_next_sources": x.get("planned_next_sources"),
            }
            for x in blind[:8]
        ],
        "domains": domains,
        "source_health": sources,
        "reading_rule": (
            "STRONG không có nghĩa dữ liệu hoàn hảo; chỉ nghĩa domain đã có độ phủ đa nguồn đủ để discovery. "
            "WEAK/BROKEN/MISSING phải làm giảm độ tự tin của mọi thesis phụ thuộc domain đó."
        ),
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"source-coverage domains={len(domains)} strong={counts.get('strong',0)} partial={counts.get('partial',0)} "
        f"weak={counts.get('weak',0)} broken={counts.get('broken',0)} missing={counts.get('missing',0)}"
    )


if __name__ == "__main__":
    main()
