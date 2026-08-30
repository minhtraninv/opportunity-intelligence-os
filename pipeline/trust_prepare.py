#!/usr/bin/env python3
"""Prepare discovery data for the V3.0.1 trust-hardened release.

This stage does not create new intelligence. It labels evidence honestly before
upstream outputs are allowed to influence public-facing conclusions:
- an official-site headline discovered from a landing page is discovery, not proof;
- curated/verified seeds are primary verified evidence;
- auto-discovered places and public bodies are not organizations.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
HISTORY = DATA / "history.json"
MEDIA = DATA / "entity_media_intelligence.json"

VIETNAM_LOCATIONS = {
    "hà nội", "tp.hcm", "tp hcm", "tp hồ chí minh", "thành phố hồ chí minh", "hồ chí minh",
    "hải phòng", "đà nẵng", "cần thơ", "huế", "quảng ninh", "cao bằng", "lạng sơn",
    "lai châu", "điện biên", "sơn la", "tuyên quang", "lào cai", "thái nguyên", "phú thọ",
    "bắc ninh", "hưng yên", "ninh bình", "thanh hóa", "nghệ an", "hà tĩnh", "quảng trị",
    "quảng ngãi", "gia lai", "khánh hòa", "lâm đồng", "đắk lắk", "đắc lắc", "đồng nai",
    "tây ninh", "vĩnh long", "đồng tháp", "cà mau", "an giang", "bình dương", "bà rịa",
    "vũng tàu", "bình định", "bình thuận", "quảng nam", "bắc giang", "vĩnh phúc",
}
FOREIGN_LOCATIONS = {
    "sri lanka", "leipzig", "singapore", "tokyo", "seoul", "bangkok", "london", "paris",
    "new york", "washington", "beijing", "bắc kinh", "shanghai", "thượng hải", "hong kong",
    "hồng kông", "india", "ấn độ", "indonesia", "malaysia", "thái lan", "nhật bản",
    "hàn quốc", "trung quốc", "hoa kỳ", "mỹ", "đức", "pháp", "anh", "australia", "úc",
}
PUBLIC_BODY_PREFIXES = (
    "cục ", "tổng cục ", "bộ ", "sở ", "ủy ban ", "ubnd ", "hđnd ", "chính phủ",
    "quốc hội", "ban quản lý ", "ban chỉ đạo ", "cơ quan ", "viện kiểm sát ", "tòa án ",
)
TRUNCATED_PUBLIC_BODY = (
    "cục đường", "cục dự", "cục thuế", "cục hải", "sở kế", "sở công", "sở tài",
)


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def save(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def norm(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def history_grade(event: dict) -> str:
    quality = event.get("signal_quality")
    if quality == "curated" or event.get("status") == "verified-seed":
        return "primary_verified"
    if quality == "candidate":
        return "official_headline_discovery"
    if quality == "reference":
        return "reference_only"
    return "noise_or_unknown"


def entity_type(label: str) -> tuple[str, bool, str | None]:
    text = norm(label)
    if text in VIETNAM_LOCATIONS or text in FOREIGN_LOCATIONS:
        return "location", False, "geography_belongs_in_regional_radar"
    if any(text.startswith(prefix) for prefix in PUBLIC_BODY_PREFIXES):
        reason = "truncated_public_body_name" if any(text.startswith(x) for x in TRUNCATED_PUBLIC_BODY) else "public_body_not_open_world_company"
        return "public_body", False, reason
    return "organization_candidate", True, None


def main() -> None:
    now = datetime.now(timezone.utc).isoformat()

    history = load(HISTORY, {"events": [], "snapshots": []})
    grade_counts = {}
    for event in history.get("events", []):
        if not isinstance(event, dict):
            continue
        grade = history_grade(event)
        event["evidence_grade"] = grade
        grade_counts[grade] = grade_counts.get(grade, 0) + 1
    history["trust_semantics"] = {
        "version": "3.0.1",
        "updated_at": now,
        "rule": "official_landing_page_headline_is_discovery_not_primary_evidence",
        "evidence_grade_counts": grade_counts,
    }
    save(HISTORY, history)

    media = load(MEDIA, {"auto_entities": [], "events": []})
    type_by_id = {}
    suppressed = 0
    for entity in media.get("auto_entities", []):
        if not isinstance(entity, dict):
            continue
        etype, eligible, reason = entity_type(entity.get("label"))
        entity["entity_type"] = etype
        entity["eligible_for_entity_convergence"] = eligible
        entity["suppression_reason"] = reason
        type_by_id[str(entity.get("id"))] = (etype, eligible, reason)
        if not eligible:
            suppressed += 1

    for event in media.get("events", []):
        if not isinstance(event, dict):
            continue
        typed = type_by_id.get(str(event.get("entity_id")))
        if typed:
            event["entity_type"], event["eligible_for_entity_convergence"], event["suppression_reason"] = typed
        event["evidence_grade"] = "media_discovery"

    media.setdefault("meta", {})["trust_patch"] = "3.0.1"
    media["trust_semantics"] = {
        "prepared_at": now,
        "auto_entities_typed": len(type_by_id),
        "auto_entities_suppressed_from_entity_convergence": suppressed,
        "rule": "locations_and_public_bodies_remain_discovery_context_but_cannot_pose_as_open_world_companies",
    }
    save(MEDIA, media)
    print(f"trust-prepare history={len(history.get('events', []))} auto_entities={len(type_by_id)} suppressed={suppressed}")


if __name__ == "__main__":
    main()
