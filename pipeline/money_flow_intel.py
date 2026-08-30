#!/usr/bin/env python3
"""V2.0.1 Vietnam Money Flow Intelligence.

Build economic themes from heterogeneous evidence while resisting false convergence.
A broad sector tag is never enough to join an event to a theme: history/procurement
items must pass contextual rules. Macro observations may carry explicit verified
`theme_tags`. Missing supply data is unknown, never assumed scarcity.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "money_flow_intelligence.json"


def load(name: str, default):
    path = DATA / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def has_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(p.casefold() in text for p in phrases)


def publisher_group(value: str | None) -> str:
    text = norm(value)
    if "thống kê" in text or "nso" in text:
        return "Cục Thống kê"
    if "chính phủ" in text:
        return "Chính phủ"
    if "evn" in text or "nsmo" in text or "điện lực" in text:
        return "EVN/NSMO"
    if "đấu thầu" in text or "mua sắm công" in text:
        return "MSC"
    if "đầu tư nước ngoài" in text:
        return "FIA"
    if "bộ tài chính" in text:
        return "Bộ Tài chính"
    if "đăng ký kinh doanh" in text or "đkkd" in text:
        return "ĐKKD"
    return str(value or "Unknown").strip() or "Unknown"


THEMES = {
    "manufacturing_expansion": {
        "label": "Mở rộng năng lực sản xuất",
        "chain": [
            "FDI/CAPEX và năng lực sản xuất mới",
            "Nhà máy tăng sản lượng và nhu cầu lao động",
            "Điện, logistics, kho bãi và nhà cung ứng phụ trợ tăng tải",
            "Nhu cầu B2B vòng 2: tuyển dụng, bảo trì, PPE, vệ sinh, đóng gói, vận chuyển",
            "Nhu cầu dân sinh vòng 3 quanh cụm sản xuất: ăn ở, đi lại, dịch vụ thiết yếu"
        ],
        "small_capital_angles": [
            "dịch vụ tuyển dụng/nhân sự ngách tại cụm sản xuất",
            "sourcing vật tư tiêu hao/PPE sau khi có đơn thật",
            "đóng gói, vận chuyển, giao nhận địa phương",
            "bảo trì/vệ sinh/facility theo hợp đồng nhỏ",
            "dịch vụ ăn uống hoặc tiện ích cho cụm lao động nếu có bằng chứng địa phương"
        ],
        "supply_proxies_needed": [
            "số nhà cung cấp mới theo địa bàn/ngành",
            "mật độ tin tuyển supplier/vendor",
            "giá thuê kho/xưởng và vacancy",
            "số doanh nghiệp dịch vụ phụ trợ mới thành lập",
            "thời gian giao hàng/báo giá của nhà cung cấp hiện hữu"
        ]
    },
    "public_infrastructure": {
        "label": "Đầu tư công & hạ tầng vật lý",
        "chain": [
            "Giải ngân vốn đầu tư công",
            "Khởi công/thi công đường, sân bay, cảng, lưới điện và công trình",
            "Nhu cầu vật liệu, máy móc, vận tải và nhà thầu phụ tăng",
            "Dịch vụ công trường, lưu trú, ăn uống, sửa chữa và hậu cần xuất hiện",
            "Giá trị đất/tài sản có thể phản ứng nhưng không được coi là cơ hội mặc định"
        ],
        "small_capital_angles": [
            "cung ứng vật tư tiêu hao theo đơn",
            "vận tải nhỏ/last-mile công trường",
            "dịch vụ lưu trú/ăn uống cho đội thi công nếu xác minh được mật độ lao động",
            "sửa chữa, bảo dưỡng, vệ sinh, an toàn lao động",
            "kết nối supplier-subcontractor thay vì ôm tài sản"
        ],
        "supply_proxies_needed": [
            "số nhà cung ứng địa phương",
            "giá và lead-time vật tư",
            "mật độ nhà trọ/dịch vụ quanh công trường",
            "số gói thầu phụ hoặc nhu cầu thuê ngoài",
            "tỷ lệ lấp đầy logistics địa phương"
        ]
    },
    "logistics_trade": {
        "label": "Gia tốc thương mại & logistics",
        "chain": [
            "Xuất nhập khẩu và sản xuất tăng",
            "Lưu lượng hàng hóa, chứng từ, kho và vận tải tăng",
            "Forwarder, kho bãi và nhà vận chuyển tăng công suất",
            "Phát sinh nhu cầu đóng gói, khai báo, gom hàng, giao nhận và phần mềm vận hành"
        ],
        "small_capital_angles": [
            "broker/kết nối vận tải có kiểm soát công nợ",
            "đóng gói và vật tư logistics theo đơn",
            "dịch vụ chứng từ/ops cho SME xuất nhập khẩu",
            "last-mile B2B tại cụm công nghiệp",
            "micro-fulfillment chỉ sau khi xác minh nhu cầu lặp lại"
        ],
        "supply_proxies_needed": [
            "giá cước theo tuyến",
            "tỷ lệ xe rỗng/chiều về",
            "giá thuê kho và vacancy",
            "thời gian xử lý chứng từ",
            "số forwarder/đơn vị vận tải mới"
        ]
    },
    "data_infrastructure": {
        "label": "Hạ tầng dữ liệu & số hóa",
        "chain": [
            "Chính sách/dòng vốn cho dữ liệu, cloud, AI và số hóa",
            "Doanh nghiệp/cơ quan mua hạ tầng, phần mềm và dịch vụ triển khai",
            "Nhu cầu tích hợp, migration, làm sạch dữ liệu, vận hành và bảo mật tăng",
            "Nhà thầu lớn cần các module/phần việc nhỏ hoặc đối tác chuyên môn"
        ],
        "small_capital_angles": [
            "data cleaning/QC/annotation có quy trình rõ",
            "tích hợp hoặc automation ngách",
            "đào tạo/vận hành/support sau triển khai",
            "sourcing nhân lực kỹ thuật theo dự án",
            "dịch vụ số hóa tài liệu chỉ khi có năng lực và compliance phù hợp"
        ],
        "supply_proxies_needed": [
            "số vendor có năng lực tương ứng",
            "mức lương/tin tuyển kỹ năng liên quan",
            "backlog triển khai của integrator",
            "giá dịch vụ theo unit",
            "tỷ lệ tender/RFP phải gia hạn hoặc ít bidder"
        ]
    },
    "energy_grid": {
        "label": "Mở rộng điện & lưới điện",
        "chain": [
            "Phụ tải điện và nhu cầu công nghiệp tăng",
            "Đầu tư nguồn/lưới/trạm và hiện đại hóa vận hành",
            "Nhu cầu thiết bị, thi công, kiểm định, bảo trì và tiết kiệm năng lượng",
            "Dịch vụ phụ trợ quanh dự án điện tăng theo địa bàn"
        ],
        "small_capital_angles": [
            "dịch vụ kiểm tra/bảo trì qua đối tác đủ chứng chỉ",
            "PPE và vật tư tiêu hao theo đơn",
            "đào tạo/ops phần mềm hoặc quản lý hồ sơ",
            "sourcing thiết bị phụ trợ không tồn kho",
            "dịch vụ tiết kiệm năng lượng chỉ khi có năng lực chuyên môn"
        ],
        "supply_proxies_needed": [
            "số nhà thầu đủ chứng chỉ tại địa bàn",
            "backlog dự án",
            "lead-time thiết bị",
            "mức thiếu hụt nhân lực điện",
            "giá dịch vụ kiểm định/bảo trì"
        ]
    },
    "consumer_services": {
        "label": "Tiêu dùng & dịch vụ",
        "chain": [
            "Thu nhập/du lịch/lưu chuyển người tác động sức mua",
            "Doanh thu dịch vụ và F&B phản ứng",
            "Mặt bằng, lao động, marketing và supply chain phản ứng sau",
            "Cơ hội chỉ đáng thử khi tăng trưởng thực vượt chi phí đầu vào và cạnh tranh"
        ],
        "small_capital_angles": [
            "dịch vụ B2B cho cửa hàng thay vì mở thêm mặt bằng",
            "sản phẩm ngách test pre-order",
            "content/performance marketing gắn doanh số",
            "sourcing sản phẩm lặp lại với tồn kho thấp"
        ],
        "supply_proxies_needed": [
            "số cửa hàng mở/đóng",
            "giá thuê mặt bằng",
            "CAC/quảng cáo",
            "traffic và search demand",
            "biên lợi nhuận sau chi phí đầu vào"
        ]
    },
    "sme_formalization": {
        "label": "SME/hộ kinh doanh chính quy hóa & số hóa",
        "chain": [
            "Quy định thuế/hóa đơn/đăng ký thay đổi",
            "Hộ kinh doanh và SME phải đổi quy trình",
            "Nhu cầu kế toán, hóa đơn, POS, inventory và SOP tăng",
            "Dịch vụ triển khai + hỗ trợ vận hành có thể tạo doanh thu lặp lại"
        ],
        "small_capital_angles": [
            "setup quy trình/hóa đơn/POS theo checklist",
            "dịch vụ bookkeeping/ops qua partner đủ chuyên môn",
            "đào tạo ngắn + hỗ trợ 14/30 ngày",
            "template/SOP và automation đơn giản"
        ],
        "supply_proxies_needed": [
            "mật độ nhà cung cấp dịch vụ tại địa phương",
            "giá dịch vụ kế toán/POS",
            "thời gian onboarding",
            "tỷ lệ hộ kinh doanh chưa chuyển đổi",
            "số câu hỏi/hỗ trợ lặp lại sau triển khai"
        ]
    }
}


CONTEXT = {
    "manufacturing_expansion": (
        "nhà máy", "khu công nghiệp", "cụm công nghiệp", "nhà xưởng", "sản xuất",
        "chế biến", "chế tạo", "công nghiệp", "dây chuyền", "công suất", "mỏ than",
        "khoáng sản", "phụ trợ", "industrial"
    ),
    "public_infrastructure": (
        "đầu tư công", "cao tốc", "sân bay", "cảng biển", "đường sắt", "vành đai",
        "cầu", "đường", "hạ tầng", "khởi công", "công trình", "giải ngân", "dự án giao thông"
    ),
    "logistics_trade": (
        "logistics", "vận tải", "kho vận", "kho bãi", "giao nhận", "forwarder", "forwarding",
        "xuất khẩu", "nhập khẩu", "xuất nhập khẩu", "kim ngạch", "cảng", "hàng hóa"
    ),
    "data_infrastructure": (
        "số hóa", "chuyển đổi số", "phần mềm", "dữ liệu", "data center", "trung tâm dữ liệu",
        "cloud", "điện toán đám mây", "ai", "trí tuệ nhân tạo", "hpc", "bán dẫn", "chip",
        "cơ sở dữ liệu", "hệ thống thông tin"
    ),
    "energy_grid": (
        "điện", "lưới điện", "trạm biến áp", "nguồn điện", "truyền tải", "evn", "nsmo",
        "điện gió", "điện mặt trời", "năng lượng", "công suất điện", "hệ thống điện"
    ),
    "consumer_services": (
        "bán lẻ", "dịch vụ tiêu dùng", "sức mua", "du lịch", "khách quốc tế", "lưu trú",
        "ăn uống", "f&b", "doanh thu dịch vụ", "tiêu dùng"
    ),
    "sme_formalization": (
        "hộ kinh doanh", "doanh nghiệp nhỏ", "doanh nghiệp vừa và nhỏ", "hóa đơn điện tử",
        "thuế khoán", "kế toán", "đăng ký doanh nghiệp", "pos", "chính quy hóa"
    )
}


def infer_history_theme_tags(event: dict) -> list[str]:
    text = norm(event.get("title"))
    categories = set(event.get("categories") or [])
    event_type = event.get("event_type")
    tags = []

    if "fdi_industrial" in categories and has_any(text, CONTEXT["manufacturing_expansion"]):
        tags.append("manufacturing_expansion")
    elif event_type == "capex_expansion" and has_any(text, CONTEXT["manufacturing_expansion"]):
        tags.append("manufacturing_expansion")
    elif "labor" in categories and has_any(text, ("nhà máy", "công nghiệp", "sản xuất", "khu công nghiệp", "chế biến", "chế tạo")):
        tags.append("manufacturing_expansion")

    if "infrastructure" in categories and has_any(text, CONTEXT["public_infrastructure"]):
        tags.append("public_infrastructure")

    if ("logistics" in categories or "trade_flow" in categories) and has_any(text, CONTEXT["logistics_trade"]):
        tags.append("logistics_trade")

    if "data_ai" in categories and has_any(text, CONTEXT["data_infrastructure"]):
        tags.append("data_infrastructure")

    if "energy" in categories and has_any(text, CONTEXT["energy_grid"]):
        tags.append("energy_grid")

    if "consumer_services" in categories and has_any(text, CONTEXT["consumer_services"]):
        tags.append("consumer_services")

    if "sme" in categories and has_any(text, CONTEXT["sme_formalization"]):
        tags.append("sme_formalization")

    return sorted(set(tags))


def evidence_from_history(history: dict) -> list[dict]:
    out = []
    family_map = {
        "capital_flow": "capital",
        "capex_expansion": "capex",
        "hiring": "labor",
        "infrastructure_delivery": "infrastructure",
        "policy_regulation": "policy",
        "business_formation": "business_formation",
        "procurement": "procurement",
        "market_data": "market_data"
    }
    for e in history.get("events", []):
        if e.get("signal_quality") not in {"candidate", "curated"}:
            continue
        theme_tags = infer_history_theme_tags(e)
        if not theme_tags:
            continue
        out.append({
            "id": e.get("id"),
            "family": family_map.get(e.get("event_type"), "other"),
            "title": e.get("title"),
            "publisher": e.get("publisher"),
            "publisher_group": publisher_group(e.get("publisher")),
            "source_url": e.get("url"),
            "quality": e.get("signal_quality"),
            "category_tags": e.get("categories", []),
            "theme_tags": theme_tags,
            "geography": e.get("geography", []),
            "observed_at": e.get("first_seen_at") or e.get("collected_at"),
            "directional": True
        })
    return out


def procurement_theme_tags(item: dict) -> list[str]:
    title = norm(item.get("title"))
    buyer = norm(item.get("buyer"))
    text = f"{title} {buyer}"
    category = item.get("procurement_category")
    tags = []

    if category == "digital_services" and has_any(text, CONTEXT["data_infrastructure"]):
        tags.append("data_infrastructure")
    if category == "logistics" and has_any(text, CONTEXT["logistics_trade"]):
        tags.append("logistics_trade")
    if category in {"maintenance", "garment_ppe"} and has_any(text, CONTEXT["manufacturing_expansion"]):
        tags.append("manufacturing_expansion")
    return tags


def evidence_from_procurement(action: dict) -> list[dict]:
    out = []
    for x in action.get("buyer_triggers", []):
        tags = procurement_theme_tags(x)
        if not tags:
            continue
        out.append({
            "id": f"proc::{x.get('id')}",
            "family": "procurement",
            "title": x.get("title"),
            "publisher": x.get("source_name", "Hệ thống mạng đấu thầu quốc gia"),
            "publisher_group": "MSC",
            "source_url": x.get("source_url"),
            "quality": "official_trigger",
            "category_tags": [x.get("procurement_category")],
            "theme_tags": tags,
            "geography": [],
            "observed_at": x.get("posted_at"),
            "buyer": x.get("buyer"),
            "package_price_vnd": x.get("package_price_vnd"),
            "directional": True
        })
    return out


def evidence_from_macro(macro: dict) -> list[dict]:
    out = []
    for x in macro.get("observations", []):
        out.append({
            "id": f"macro::{x.get('id')}",
            "family": x.get("family", "macro"),
            "title": x.get("title"),
            "publisher": x.get("publisher"),
            "publisher_group": publisher_group(x.get("publisher")),
            "source_url": x.get("source_url"),
            "quality": x.get("quality", "official_verified"),
            "category_tags": [],
            "theme_tags": x.get("theme_tags", []),
            "geography": x.get("geography", []),
            "observed_at": x.get("period"),
            "metric": x.get("metric"),
            "value": x.get("value"),
            "unit": x.get("unit"),
            "direction": x.get("direction"),
            "notes": x.get("notes"),
            "directional": x.get("direction") not in {"level_observation", "unknown", None}
        })
    return out


def dedupe_evidence(items: list[dict]) -> list[dict]:
    """Prefer macro verified evidence over duplicate history observations of same source/family."""
    rank = {"official_verified": 4, "curated": 3, "candidate": 2, "official_trigger": 1}
    best = {}
    for item in items:
        key = (item.get("source_url") or item.get("id"), item.get("family"))
        current = best.get(key)
        if current is None or rank.get(item.get("quality"), 0) > rank.get(current.get("quality"), 0):
            best[key] = item
    return list(best.values())


def theme_score(items: list[dict]) -> tuple[int, str, list[str], list[str], list[str]]:
    directional = [x for x in items if x.get("directional")]
    families = sorted({x.get("family") for x in directional if x.get("family") not in {None, "other"}})
    publishers = sorted({x.get("publisher_group") or publisher_group(x.get("publisher")) for x in directional if x.get("publisher")})
    non_proc_publishers = sorted({x.get("publisher_group") for x in directional if x.get("family") != "procurement" and x.get("publisher_group")})
    verified = sum(1 for x in directional if x.get("quality") in {"official_verified", "curated"})

    score = 10 + min(len(families), 6) * 10 + min(len(publishers), 5) * 5 + min(verified, 4) * 3
    score = min(90, score)

    # Strong status requires independent evidence families AND independent source institutions.
    if len(families) >= 4 and len(publishers) >= 3 and len(non_proc_publishers) >= 2:
        status = "converging"
    elif len(families) >= 3 and len(publishers) >= 2:
        status = "developing"
    elif len(families) >= 2:
        status = "early"
    else:
        status = "insufficient"

    # Procurement can corroborate demand but can never make a theme converge by itself.
    if families == ["procurement"]:
        score = min(score, 25)
        status = "insufficient"
    return score, status, families, publishers, non_proc_publishers


def main() -> None:
    macro = load("macro_observations.json", {})
    history = load("history.json", {})
    action = load("action_intelligence.json", {})

    evidence = dedupe_evidence(
        evidence_from_macro(macro) + evidence_from_history(history) + evidence_from_procurement(action)
    )

    themes = []
    for key, spec in THEMES.items():
        matched = [x for x in evidence if key in set(x.get("theme_tags", []))]
        proc = [x for x in matched if x.get("family") == "procurement"][:4]
        non_proc = [x for x in matched if x.get("family") != "procurement"]
        shown = (non_proc + proc)[:12]
        score, status, families, publishers, non_proc_publishers = theme_score(matched)

        supply_families = {"business_formation", "supply", "pricing", "capacity", "vacancy"}
        observed_supply = sorted(set(families) & supply_families)
        gap_status = "investigate_gap" if status in {"converging", "developing"} and observed_supply else "unconfirmed_supply_gap"

        themes.append({
            "id": key,
            "label": spec["label"],
            "score": score,
            "status": status,
            "evidence_count": len(matched),
            "directional_evidence_count": sum(1 for x in matched if x.get("directional")),
            "independent_families": families,
            "independent_publishers": publishers,
            "non_procurement_publishers": non_proc_publishers,
            "economic_chain": spec["chain"],
            "small_capital_angles": spec["small_capital_angles"],
            "evidence": shown,
            "supply_gap": {
                "status": gap_status,
                "supply_evidence_families": observed_supply,
                "proxies_needed": spec["supply_proxies_needed"],
                "rule": "Không có dữ liệu cung không đồng nghĩa thiếu cung. Chỉ nâng thành gap khi demand tăng và có proxy cung xác nhận phản ứng chậm."
            }
        })

    themes.sort(key=lambda x: (-x["score"], -len(x["independent_families"]), x["label"]))
    strongest = themes[0] if themes else None
    if strongest and strongest["status"] in {"converging", "developing"}:
        thesis = (
            f"Theme đáng điều tra nhất hiện tại: {strongest['label']} ({strongest['status']}, "
            f"{len(strongest['independent_families'])} họ bằng chứng, {len(strongest['independent_publishers'])} nhóm nguồn). "
            "Đây là chuyển động kinh tế cần đào sâu; chưa được gọi là cơ hội cho tới khi xác minh supply gap, buyer và economics."
        )
    else:
        thesis = "Chưa có theme nào đủ hội tụ đa nguồn. Tiếp tục tích lũy bằng chứng; không ép hệ thống tạo câu chuyện."

    payload = {
        "meta": {
            "version": "2.0.1",
            "generated_at": now_iso(),
            "mode": "contextual_theme_chain_supply_gap_intelligence",
            "principle": "broad_sector_tags_cannot_create_theme_membership_without_context"
        },
        "thesis": thesis,
        "coverage": {
            "total_evidence_inputs": len(evidence),
            "macro_observations": len(macro.get("observations", [])),
            "contextual_history_evidence": len(evidence_from_history(history)),
            "contextual_procurement_support": len(evidence_from_procurement(action)),
            "themes": len(themes),
            "themes_converging": sum(1 for x in themes if x["status"] == "converging"),
            "themes_developing": sum(1 for x in themes if x["status"] == "developing"),
            "supply_gaps_confirmed": 0
        },
        "themes": themes,
        "guardrails": [
            "A broad sector tag cannot create theme membership without contextual evidence.",
            "Procurement is corroborating evidence, not the center of V2.0.",
            "Single-point level observations are context only, not trend families.",
            "No supply evidence != supply shortage.",
            "A theme is not an opportunity until a buyer, offer, economics and small test are identified.",
            "Independent evidence families and institutions matter more than raw headline count.",
            "Contradictory evidence must be retained rather than hidden."
        ]
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"money-flow v2.0.1 themes={len(themes)} evidence={len(evidence)} "
        f"converging={payload['coverage']['themes_converging']} developing={payload['coverage']['themes_developing']}"
    )


if __name__ == "__main__":
    main()
