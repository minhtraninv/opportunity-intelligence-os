#!/usr/bin/env python3
"""V2.0 Vietnam Money Flow Intelligence.

Turns heterogeneous evidence into economic themes without pretending that missing
supply-side data is a confirmed opportunity. Procurement remains supporting evidence,
not the center of the system.
"""
from __future__ import annotations

import json
from collections import Counter
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


THEMES = {
    "manufacturing_expansion": {
        "label": "Mở rộng năng lực sản xuất",
        "category_tags": {"fdi_industrial", "energy", "logistics", "labor"},
        "chain": [
            "FDI/CAPEX và năng lực sản xuất mới",
            "Nhà máy tăng sản lượng và nhu cầu lao động",
            "Điện, logistics, kho bãi và nhà cung ứng phụ trợ tăng tải",
            "Nhu cầu B2B vòng 2: tuyển dụng, bảo trì, PPE, vệ sinh, đóng gói, vận chuyển",
            "Nhu cầu dân sinh vòng 3 quanh cụm sản xuất: ăn ở, đi lại, dịch vụ thiết yếu"
        ],
        "small_capital_angles": [
            "dịch vụ tuyển dụng/nhân sự ngách",
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
        "category_tags": {"infrastructure", "logistics", "construction"},
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
        "category_tags": {"logistics", "fdi_industrial", "trade_flow"},
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
        "category_tags": {"data_ai", "digital_services", "energy"},
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
        "category_tags": {"energy", "infrastructure"},
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
        "category_tags": {"consumer_services", "sme"},
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
        "category_tags": {"sme", "digital_services"},
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


def evidence_from_history(history: dict) -> list[dict]:
    out = []
    for e in history.get("events", []):
        if e.get("signal_quality") not in {"candidate", "curated"}:
            continue
        family = {
            "capital_flow": "capital",
            "capex_expansion": "capex",
            "hiring": "labor",
            "infrastructure_delivery": "infrastructure",
            "policy_regulation": "policy",
            "business_formation": "business_formation",
            "procurement": "procurement",
            "market_data": "market_data"
        }.get(e.get("event_type"), "other")
        out.append({
            "id": e.get("id"),
            "family": family,
            "title": e.get("title"),
            "publisher": e.get("publisher"),
            "source_url": e.get("url"),
            "quality": e.get("signal_quality"),
            "category_tags": e.get("categories", []),
            "theme_tags": [],
            "geography": e.get("geography", []),
            "observed_at": e.get("first_seen_at") or e.get("collected_at")
        })
    return out


def evidence_from_procurement(action: dict) -> list[dict]:
    out = []
    category_theme = {
        "digital_services": "data_infrastructure",
        "logistics": "logistics_trade",
        "maintenance": "manufacturing_expansion",
        "garment_ppe": "manufacturing_expansion"
    }
    for x in action.get("buyer_triggers", []):
        theme = category_theme.get(x.get("procurement_category"))
        if not theme:
            continue
        out.append({
            "id": f"proc::{x.get('id')}",
            "family": "procurement",
            "title": x.get("title"),
            "publisher": x.get("source_name", "Hệ thống mạng đấu thầu quốc gia"),
            "source_url": x.get("source_url"),
            "quality": "official_trigger",
            "category_tags": [x.get("procurement_category")],
            "theme_tags": [theme],
            "geography": [],
            "observed_at": x.get("posted_at"),
            "buyer": x.get("buyer"),
            "package_price_vnd": x.get("package_price_vnd")
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
            "notes": x.get("notes")
        })
    return out


def theme_matches(ev: dict, key: str, spec: dict) -> bool:
    if key in set(ev.get("theme_tags", [])):
        return True
    return bool(set(ev.get("category_tags", [])) & spec["category_tags"])


def theme_score(items: list[dict]) -> tuple[int, str, list[str], list[str]]:
    families = sorted({x.get("family") for x in items if x.get("family") and x.get("family") != "other"})
    publishers = sorted({x.get("publisher") for x in items if x.get("publisher")})
    verified = sum(1 for x in items if x.get("quality") in {"official_verified", "curated"})
    procurement_only = families == ["procurement"]

    score = min(92, 12 + min(len(families), 7) * 9 + min(len(publishers), 5) * 4 + min(verified, 5) * 4)
    if procurement_only:
        score = min(score, 35)
    if len(families) >= 4 and len(publishers) >= 3:
        status = "converging"
    elif len(families) >= 3:
        status = "developing"
    elif len(families) >= 2:
        status = "early"
    else:
        status = "insufficient"
    return score, status, families, publishers


def main() -> None:
    macro = load("macro_observations.json", {})
    history = load("history.json", {})
    action = load("action_intelligence.json", {})

    evidence = evidence_from_macro(macro) + evidence_from_history(history) + evidence_from_procurement(action)

    themes = []
    for key, spec in THEMES.items():
        matched = [x for x in evidence if theme_matches(x, key, spec)]
        # Keep procurement from overwhelming the evidence list.
        proc = [x for x in matched if x.get("family") == "procurement"][:5]
        non_proc = [x for x in matched if x.get("family") != "procurement"]
        shown = (non_proc + proc)[:12]
        score, status, families, publishers = theme_score(matched)

        # Supply-gap discipline: absence of supply evidence is unknown, not scarcity.
        supply_families = {"business_formation", "supply", "pricing", "capacity", "vacancy"}
        observed_supply = sorted(set(families) & supply_families)
        if status in {"converging", "developing"} and observed_supply:
            gap_status = "investigate_gap"
        else:
            gap_status = "unconfirmed_supply_gap"

        themes.append({
            "id": key,
            "label": spec["label"],
            "score": score,
            "status": status,
            "evidence_count": len(matched),
            "independent_families": families,
            "independent_publishers": publishers,
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
            f"Theme mạnh nhất hiện tại: {strongest['label']} ({strongest['status']}, "
            f"{len(strongest['independent_families'])} họ bằng chứng độc lập). "
            "Đây là nơi nên đào sâu chuỗi kinh tế; chưa được gọi là cơ hội cho tới khi xác minh supply gap và buyer cụ thể."
        )
    else:
        thesis = "Chưa có theme nào đủ hội tụ đa nguồn. Tiếp tục tích lũy bằng chứng; không ép hệ thống tạo câu chuyện."

    payload = {
        "meta": {
            "version": "2.0.0",
            "generated_at": now_iso(),
            "mode": "theme_chain_supply_gap_intelligence",
            "principle": "detect_where_money_is_moving_before_translating_to_small_capital_opportunities"
        },
        "thesis": thesis,
        "coverage": {
            "total_evidence_inputs": len(evidence),
            "macro_observations": len(macro.get("observations", [])),
            "historical_candidate_or_curated_events": len(evidence_from_history(history)),
            "procurement_supporting_triggers": len(evidence_from_procurement(action)),
            "themes": len(themes),
            "themes_converging": sum(1 for x in themes if x["status"] == "converging"),
            "supply_gaps_confirmed": sum(1 for x in themes if x["supply_gap"]["status"] == "confirmed_gap")
        },
        "themes": themes,
        "guardrails": [
            "Procurement is supporting evidence, not the center of V2.0.",
            "No supply evidence != supply shortage.",
            "A theme is not an opportunity until a buyer, offer, economics and small test are identified.",
            "Independent evidence families matter more than raw headline count.",
            "Contradictory evidence must be retained rather than hidden."
        ]
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"money-flow themes={len(themes)} evidence={len(evidence)} "
        f"converging={payload['coverage']['themes_converging']}"
    )


if __name__ == "__main__":
    main()
