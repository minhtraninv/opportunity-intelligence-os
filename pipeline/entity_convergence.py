#!/usr/bin/env python3
"""Build open-world cross-domain entity convergence intelligence.

The purpose is discovery, not recommendation. Known aliases come from the curated
registry, but conservative auto-discovered organizations can also enter from the
media discovery layer. Neither registry membership nor auto-discovery contributes
importance by itself. Media can create discovery-level attention; high convergence
still requires at least one primary/official evidence item.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REGISTRY_PATH = DATA / "entity_registry.json"
HISTORY_PATH = DATA / "history.json"
CORPORATE_PATH = DATA / "corporate_intelligence.json"
MEDIA_PATH = DATA / "entity_media_intelligence.json"
MONEY_PATH = DATA / "money_flow_intelligence.json"
REGIONAL_PATH = DATA / "regional_intelligence.json"
OUTPUT = DATA / "entity_convergence_intelligence.json"

WINDOW_DAYS = 120
MAX_EVIDENCE_PER_FAMILY = 3

FAMILY_WEIGHT = {
    "policy": 18,
    "capital": 20,
    "project_execution": 22,
    "strategy": 18,
    "operating": 16,
    "labor": 12,
    "business_formation": 8,
    "procurement": 5,
}

EVENT_FAMILY = {
    "policy_regulation": "policy",
    "capital_flow": "capital",
    "capex_expansion": "project_execution",
    "infrastructure_delivery": "project_execution",
    "hiring": "labor",
    "business_formation": "business_formation",
    "market_data": "operating",
    "procurement": "procurement",
}

CORPORATE_FAMILY = {
    "capital_raise": "capital",
    "financing": "capital",
    "capex_project": "project_execution",
    "contract_award": "project_execution",
    "acquisition_investment": "strategy",
}

CATEGORY_THEME = {
    "fdi_industrial": "manufacturing_expansion",
    "construction": "public_infrastructure",
    "infrastructure": "public_infrastructure",
    "logistics": "logistics_trade",
    "trade_flow": "logistics_trade",
    "sme": "sme_formalization",
    "data_ai": "data_infrastructure",
    "energy": "energy_grid",
    "consumer_services": "consumer_services",
}

PRIMARY_ORIGINS = {"normalized_public_signal", "official_corporate_disclosure"}


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def parse_dt(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def alias_match(text: str, aliases: list[str]) -> bool:
    value = str(text or "")
    for alias in aliases:
        pattern = rf"(?<!\w){re.escape(str(alias))}(?!\w)"
        if re.search(pattern, value, flags=re.IGNORECASE | re.UNICODE):
            return True
    return False


def evidence_age_days(item: dict, now: datetime) -> int | None:
    dt = parse_dt(item.get("published_at") or item.get("observed_at") or item.get("first_seen_at") or item.get("collected_at"))
    if not dt:
        return None
    return max(0, (now - dt).days)


def theme_labels(money: dict) -> dict[str, str]:
    return {
        str(x.get("theme_id")): str(x.get("label") or x.get("theme_id"))
        for x in money.get("themes", []) if isinstance(x, dict) and x.get("theme_id")
    }


def regional_state(regional: dict) -> dict[str, dict]:
    return {
        str(x.get("region")): x
        for x in regional.get("regions", []) if isinstance(x, dict) and x.get("region")
    }


def add_history_evidence(entity: dict, history: dict, now: datetime) -> list[dict]:
    rows = []
    aliases = entity.get("aliases") or []
    cutoff = now - timedelta(days=WINDOW_DAYS)
    for event in history.get("events", []):
        if not isinstance(event, dict):
            continue
        if event.get("signal_quality") not in {"curated", "candidate"}:
            continue
        family = EVENT_FAMILY.get(event.get("event_type"))
        if not family:
            continue
        title = str(event.get("title") or "")
        if not alias_match(title, aliases):
            continue
        dt = parse_dt(event.get("first_seen_at") or event.get("collected_at"))
        if dt and dt < cutoff:
            continue
        rows.append({
            "id": event.get("id"),
            "family": family,
            "title": title,
            "publisher": event.get("publisher"),
            "source_url": event.get("url"),
            "observed_at": (dt.isoformat() if dt else None),
            "categories": event.get("categories") or [],
            "geography": event.get("geography") or [],
            "quality": event.get("signal_quality"),
            "origin": "normalized_public_signal",
        })
    return rows


def add_corporate_evidence(entity: dict, corporate: dict, now: datetime) -> list[dict]:
    rows = []
    aliases = entity.get("aliases") or []
    cutoff = now - timedelta(days=WINDOW_DAYS)
    for event in corporate.get("buyer_triggers", []):
        if not isinstance(event, dict):
            continue
        family = CORPORATE_FAMILY.get(event.get("event_type"))
        if not family:
            continue
        text = f"{event.get('ticker') or ''} {event.get('title') or ''}"
        if not alias_match(text, aliases):
            continue
        dt = parse_dt(event.get("published_at") or event.get("first_seen_at"))
        if dt and dt < cutoff:
            continue
        rows.append({
            "id": event.get("id"),
            "family": family,
            "title": str(event.get("title") or ""),
            "publisher": event.get("source_name") or "Official corporate disclosure",
            "source_url": event.get("source_url"),
            "observed_at": (dt.isoformat() if dt else None),
            "categories": [],
            "geography": [],
            "quality": "official_trigger",
            "origin": "official_corporate_disclosure",
        })
    return rows


def add_media_evidence(entity: dict, media: dict, now: datetime) -> list[dict]:
    rows = []
    cutoff = now - timedelta(days=WINDOW_DAYS)
    for event in media.get("events", []):
        if not isinstance(event, dict) or event.get("entity_id") != entity.get("id"):
            continue
        family = event.get("family")
        if family not in FAMILY_WEIGHT:
            continue
        dt = parse_dt(event.get("published_at") or event.get("first_seen_at"))
        if dt and dt < cutoff:
            continue
        rows.append({
            "id": event.get("id"),
            "event_signature": event.get("event_signature"),
            "family": family,
            "title": str(event.get("title") or ""),
            "publisher": event.get("publisher"),
            "source_url": event.get("source_url"),
            "observed_at": (dt.isoformat() if dt else None),
            "categories": [],
            "geography": [],
            "quality": "media_discovery",
            "origin": "media_discovery",
        })
    return rows


def dedupe_and_cap(rows: list[dict]) -> list[dict]:
    deduped = {}
    for row in rows:
        if row.get("origin") == "media_discovery" and row.get("event_signature"):
            key = f"media:{row.get('event_signature')}"
        else:
            key = row.get("id") or (row.get("family"), row.get("title"), row.get("source_url"))
        current = deduped.get(str(key))
        if current is None or (row.get("origin") in PRIMARY_ORIGINS and current.get("origin") not in PRIMARY_ORIGINS):
            deduped[str(key)] = row

    grouped = defaultdict(list)
    for row in deduped.values():
        grouped[row.get("family")].append(row)

    output = []
    for family, family_rows in grouped.items():
        family_rows.sort(key=lambda x: x.get("observed_at") or "", reverse=True)
        limit = 1 if family == "procurement" else MAX_EVIDENCE_PER_FAMILY
        output.extend(family_rows[:limit])
    output.sort(key=lambda x: x.get("observed_at") or "", reverse=True)
    return output


def linked_context(evidence: list[dict], money: dict, regional: dict) -> tuple[list[dict], list[dict]]:
    labels = theme_labels(money)
    theme_ids = []
    regions = []
    for row in evidence:
        for category in row.get("categories") or []:
            theme_id = CATEGORY_THEME.get(category)
            if theme_id and theme_id not in theme_ids:
                theme_ids.append(theme_id)
        for region in row.get("geography") or []:
            if region not in regions:
                regions.append(region)

    money_map = {x.get("theme_id"): x for x in money.get("themes", []) if isinstance(x, dict)}
    theme_context = []
    for theme_id in theme_ids:
        theme = money_map.get(theme_id, {})
        theme_context.append({
            "theme_id": theme_id,
            "label": labels.get(theme_id, theme_id),
            "score": theme.get("score"),
            "status": theme.get("status"),
        })

    regional_map = regional_state(regional)
    region_context = []
    for region in regions:
        row = regional_map.get(region)
        if row:
            region_context.append({
                "region": region,
                "state": row.get("state"),
                "iip_7m_yoy_pct": row.get("iip_7m_yoy_pct"),
                "fdi_yoy_pct": row.get("fdi_yoy_pct"),
            })
    return theme_context, region_context


def convergence_score(evidence: list[dict], theme_context: list[dict], region_context: list[dict], now: datetime) -> tuple[int, dict]:
    families = sorted({x.get("family") for x in evidence if x.get("family") in FAMILY_WEIGHT})
    core_families = [x for x in families if x != "procurement"]
    publishers = sorted({str(x.get("publisher")) for x in evidence if x.get("publisher")})
    primary_evidence = [x for x in evidence if x.get("origin") in PRIMARY_ORIGINS]
    media_evidence = [x for x in evidence if x.get("origin") == "media_discovery"]

    family_score = 0
    for family in core_families:
        family_rows = [x for x in evidence if x.get("family") == family]
        has_primary = any(x.get("origin") in PRIMARY_ORIGINS for x in family_rows)
        weight = FAMILY_WEIGHT[family]
        family_score += weight if has_primary else round(weight * 0.60)
    if "procurement" in families:
        family_score += 5
    family_score = min(70, family_score)

    publisher_score = min(10, max(0, len(publishers) - 1) * 3)
    event_score = min(8, len(evidence) * 2)

    newest_age = None
    for row in evidence:
        age = evidence_age_days(row, now)
        if age is not None and (newest_age is None or age < newest_age):
            newest_age = age
    freshness_score = 0
    if newest_age is not None:
        freshness_score = 6 if newest_age <= 7 else 4 if newest_age <= 30 else 2 if newest_age <= 90 else 0

    context_score = min(4, len(theme_context) * 2) + min(4, len(region_context) * 2)
    score = min(100, family_score + publisher_score + event_score + freshness_score + context_score)
    detail = {
        "families": families,
        "core_families": core_families,
        "publishers": publishers,
        "event_count": len(evidence),
        "primary_evidence_count": len(primary_evidence),
        "media_evidence_count": len(media_evidence),
        "newest_evidence_age_days": newest_age,
    }
    return score, detail


def status_for(score: int, detail: dict) -> str:
    family_count = len(detail.get("core_families") or [])
    publisher_count = len(detail.get("publishers") or [])
    event_count = int(detail.get("event_count") or 0)
    primary_count = int(detail.get("primary_evidence_count") or 0)
    media_count = int(detail.get("media_evidence_count") or 0)
    if score >= 72 and family_count >= 3 and publisher_count >= 2 and event_count >= 3 and primary_count >= 1:
        return "high_convergence"
    if score >= 52 and family_count >= 2 and event_count >= 2 and primary_count >= 1:
        return "converging"
    if score >= 42 and family_count >= 2 and event_count >= 2 and media_count >= 2:
        return "discovery_convergence"
    if event_count >= 1:
        return "watch"
    return "not_observed"


def anomaly_flags(detail: dict, evidence: list[dict]) -> list[str]:
    families = set(detail.get("families") or [])
    flags = []
    if {"policy", "project_execution"}.issubset(families):
        flags.append("policy_execution_alignment")
    if {"capital", "project_execution"}.issubset(families):
        flags.append("capital_execution_alignment")
    if {"strategy", "project_execution"}.issubset(families):
        flags.append("strategy_execution_alignment")
    dates = [parse_dt(x.get("observed_at")) for x in evidence]
    dates = [x for x in dates if x]
    if len(dates) >= 2 and (max(dates) - min(dates)).days >= 30:
        flags.append("persistent_multi_period_attention")
    if int(detail.get("primary_evidence_count") or 0) == 0 and int(detail.get("media_evidence_count") or 0) >= 2:
        flags.append("media_only_needs_primary_verification")
    return flags


def why_now(label: str, status: str, detail: dict, theme_context: list[dict], region_context: list[dict]) -> str:
    families = detail.get("core_families") or []
    if status == "high_convergence":
        return f"{label} đang xuất hiện đồng thời trong {len(families)} họ bằng chứng độc lập và đã có bằng chứng primary. Đây là điểm hội tụ cần điều tra sâu, không phải khuyến nghị hành động."
    if status == "converging":
        return f"{label} đã có ít nhất hai loại bằng chứng khác nhau cùng chỉ tới, trong đó có evidence primary. Cần kiểm tra đây là thay đổi cấu trúc hay chỉ là nhiều biểu hiện của cùng một sự kiện."
    if status == "discovery_convergence":
        return f"{label} đang xuất hiện trong nhiều loại câu chuyện kinh tế từ media discovery. Đây là tín hiệu 'đừng bỏ qua', nhưng chưa được nâng cấp cho tới khi có nguồn primary/official xác nhận."
    if status == "watch":
        extra = ""
        if theme_context or region_context:
            extra = " Bối cảnh ngành/địa bàn liên quan cũng đang có chuyển động, nhưng bằng chứng trực tiếp về entity vẫn còn mỏng."
        return f"{label} đã xuất hiện trong radar nhưng chưa đủ họ bằng chứng để gọi là hội tụ.{extra}"
    return f"Chưa có bằng chứng trực tiếp đủ mới quanh {label}."


def main() -> None:
    now = datetime.now(timezone.utc)
    registry = [x for x in load(REGISTRY_PATH, {}).get("entities", []) if isinstance(x, dict)]
    history = load(HISTORY_PATH, {})
    corporate = load(CORPORATE_PATH, {})
    media = load(MEDIA_PATH, {})
    money = load(MONEY_PATH, {})
    regional = load(REGIONAL_PATH, {})

    registry_ids = {str(x.get("id")) for x in registry if x.get("id")}
    auto_entities = []
    for entity in media.get("auto_entities", []):
        if not isinstance(entity, dict) or not entity.get("id") or not entity.get("aliases"):
            continue
        if str(entity.get("id")) in registry_ids:
            continue
        auto_entities.append(entity)

    entities = [(x, "curated_registry") for x in registry]
    entities.extend((x, "auto_discovered") for x in auto_entities)

    rows = []
    for entity, entity_origin in entities:
        if not entity.get("id") or not entity.get("aliases"):
            continue
        evidence = add_history_evidence(entity, history, now)
        evidence.extend(add_corporate_evidence(entity, corporate, now))
        evidence.extend(add_media_evidence(entity, media, now))
        evidence = dedupe_and_cap(evidence)
        theme_context, region_context = linked_context(evidence, money, regional)
        score, detail = convergence_score(evidence, theme_context, region_context, now)
        status = status_for(score, detail)
        if status == "not_observed":
            continue

        # Unknown names must repeat across independent publishers before a weak WATCH
        # can reach the public radar. Stronger convergence states keep their own gates.
        if entity_origin == "auto_discovered" and status == "watch":
            if int(detail.get("event_count") or 0) < 2 or len(detail.get("publishers") or []) < 2:
                continue

        rows.append({
            "entity_id": entity.get("id"),
            "label": entity.get("label"),
            "entity_type": entity.get("entity_type"),
            "entity_origin": entity_origin,
            "status": status,
            "convergence_score": score,
            "why_now": why_now(entity.get("label"), status, detail, theme_context, region_context),
            "evidence_families": detail.get("families"),
            "independent_publishers": detail.get("publishers"),
            "event_count": detail.get("event_count"),
            "primary_evidence_count": detail.get("primary_evidence_count"),
            "media_evidence_count": detail.get("media_evidence_count"),
            "newest_evidence_age_days": detail.get("newest_evidence_age_days"),
            "anomaly_flags": anomaly_flags(detail, evidence),
            "theme_context": theme_context,
            "regional_context": region_context,
            "evidence": evidence[:8],
            "investigation_questions": [
                "Các bằng chứng này có thật sự độc lập hay chỉ là nhiều bài viết về cùng một sự kiện?",
                "Entity này đang nhận lợi ích trực tiếp, chịu chi phí, hay chỉ xuất hiện cạnh dòng tiền lớn?",
                "Có bằng chứng vận hành/CAPEX/khách hàng/doanh thu nào xác nhận câu chuyện không?",
                "Nếu hiện chỉ là media discovery, nguồn primary nào cần mở để xác minh?",
                "Điều gì phải xảy ra để thesis bị hạ cấp?",
                "Người nhìn từ tài chính, kinh doanh, nghề nghiệp hoặc công nghệ có thể rút ra câu hỏi nghiên cứu nào khác nhau?"
            ],
            "do_not_infer": [
                "convergence không đồng nghĩa cơ hội đầu tư",
                "xuất hiện nhiều không đồng nghĩa được ưu ái hoặc chắc chắn hưởng lợi",
                "media discovery không phải bằng chứng primary",
                "auto-discovered entity chỉ là candidate tên tổ chức, không phải xác nhận pháp nhân",
                "bối cảnh ngành/địa bàn không phải bằng chứng doanh thu của entity",
                "procurement được giới hạn trọng số và không thể tự tạo high convergence"
            ]
        })

    rows.sort(key=lambda x: (x.get("convergence_score", 0), x.get("primary_evidence_count", 0), x.get("event_count", 0)), reverse=True)
    coverage = {
        "registry_entities": len(registry),
        "auto_discovered_entities": len(auto_entities),
        "candidate_entities_total": len(registry) + len(auto_entities),
        "observed_entities": len(rows),
        "observed_auto_entities": sum(1 for x in rows if x.get("entity_origin") == "auto_discovered"),
        "high_convergence": sum(1 for x in rows if x.get("status") == "high_convergence"),
        "converging": sum(1 for x in rows if x.get("status") == "converging"),
        "discovery_convergence": sum(1 for x in rows if x.get("status") == "discovery_convergence"),
        "watch": sum(1 for x in rows if x.get("status") == "watch"),
        "window_days": WINDOW_DAYS,
    }
    payload = {
        "meta": {
            "version": "2.7.0",
            "generated_at": now.isoformat(),
            "mode": "open_world_cross_domain_entity_convergence",
            "principle": "unknown_entities_may_enter_but_importance_requires_independent_evidence"
        },
        "thesis": (
            "Entity Convergence không còn bị giới hạn bởi danh sách biết trước: candidate mới có thể tự xuất hiện từ dòng tin. "
            "Media giúp giảm blind spot; high convergence vẫn cần primary evidence. Mục tiêu là 'đừng bỏ qua', không phải 'hãy mua/làm'."
        ),
        "coverage": coverage,
        "entities": rows[:30],
        "reading_rule": (
            "Registry chỉ chuẩn hóa alias. Auto-discovered entity phải lặp lại đủ mạnh mới được hiện. Media có quyền tạo discovery convergence "
            "nhưng không có quyền tạo high convergence một mình. Một nguồn, một headline hoặc nhiều gói procurement không đủ."
        )
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"entity-convergence candidates={coverage['candidate_entities_total']} observed={coverage['observed_entities']} "
        f"auto={coverage['observed_auto_entities']} discovery={coverage['discovery_convergence']} "
        f"converging={coverage['converging']} high={coverage['high_convergence']}"
    )


if __name__ == "__main__":
    main()
