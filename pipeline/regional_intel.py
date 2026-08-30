#!/usr/bin/env python3
"""V2.2 Regional Money Flow Intelligence.

Crosses production momentum with registered FDI flow. It explicitly distinguishes
new-capital acceleration from output growth of an existing industrial base.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCE = DATA / "regional_observations.json"
OUT = DATA / "regional_intelligence.json"


def load() -> dict:
    try:
        value = json.loads(SOURCE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def classify(iip, fdi_yoy):
    if iip is not None and fdi_yoy is not None:
        if iip >= 15 and fdi_yoy >= 25:
            return "dual_acceleration"
        if iip >= 15 and fdi_yoy < 0:
            return "production_strong_capital_cooling"
        if iip >= 10 and fdi_yoy >= 0:
            return "dual_positive"
        return "mixed_confirmed"
    if iip is not None:
        return "production_acceleration_capital_unconfirmed" if iip >= 15 else "production_observed_capital_unconfirmed"
    if fdi_yoy is not None:
        if fdi_yoy >= 25:
            return "capital_acceleration_sector_unconfirmed"
        if fdi_yoy < 0:
            return "capital_cooling_production_unconfirmed"
        return "capital_positive_production_unconfirmed"
    return "insufficient"


def score_row(state, iip, fdi_yoy, fdi_abs):
    score = {
        "dual_acceleration": 82,
        "dual_positive": 70,
        "production_strong_capital_cooling": 62,
        "production_acceleration_capital_unconfirmed": 55,
        "capital_acceleration_sector_unconfirmed": 50,
        "mixed_confirmed": 45,
        "capital_positive_production_unconfirmed": 40,
        "production_observed_capital_unconfirmed": 38,
        "capital_cooling_production_unconfirmed": 25,
        "insufficient": 10,
    }.get(state, 10)
    if state == "dual_acceleration":
        if (iip or 0) >= 20:
            score += 4
        if (fdi_yoy or 0) >= 100:
            score += 4
        if (fdi_abs or 0) >= 2000:
            score += 4
    elif state == "production_strong_capital_cooling" and (iip or 0) >= 20:
        score += 4
    elif state == "production_acceleration_capital_unconfirmed" and (iip or 0) >= 25:
        score += 5
    elif state == "capital_acceleration_sector_unconfirmed" and (fdi_abs or 0) >= 3000:
        score += 5
    return min(score, 94)


def interpretation(state):
    return {
        "dual_acceleration": "Sản lượng công nghiệp và dòng FDI đăng ký cùng tăng mạnh. Đây là cụm ưu tiên điều tra tác động vòng 2, nhưng vẫn cần xác nhận ngành FDI, tuyển dụng và công suất KCN.",
        "dual_positive": "Cả sản xuất và FDI đều tích cực nhưng chưa đủ mạnh để gọi là gia tốc kép.",
        "production_strong_capital_cooling": "Sản xuất tăng mạnh trong khi FDI đăng ký mới giảm. Có thể là ramp-up công suất sẵn có/đầu tư đã cam kết trước đó; không nên kể câu chuyện 'vốn mới đang đổ vào' mà chưa có bằng chứng khác.",
        "production_acceleration_capital_unconfirmed": "Sản xuất tăng nhanh nhưng dataset hiện chưa có FDI địa phương đủ để xác nhận dòng vốn mới. Cần kiểm tra CAPEX/FDI/tuyển dụng trước khi nâng thesis.",
        "capital_acceleration_sector_unconfirmed": "FDI tổng đăng ký tăng mạnh nhưng chưa xác nhận bao nhiêu thuộc sản xuất. Cần đọc cơ cấu ngành/dự án trước khi gắn vào manufacturing theme.",
        "capital_cooling_production_unconfirmed": "FDI đăng ký giảm và chưa có production signal trong snapshot này; ưu tiên thấp cho đến khi có bằng chứng trái chiều.",
        "mixed_confirmed": "Hai tín hiệu đã có nhưng không cùng chiều đủ rõ; giữ trạng thái mixed.",
        "capital_positive_production_unconfirmed": "FDI tích cực nhưng chưa có production confirmation.",
        "production_observed_capital_unconfirmed": "Có production signal nhưng chưa có capital confirmation.",
        "insufficient": "Chưa đủ dữ liệu."
    }.get(state, "Cần thêm bằng chứng.")


def main():
    src = load()
    rows = []
    for x in src.get("observations", []):
        iip = x.get("iip_7m_yoy_pct")
        fdi_yoy = x.get("fdi_yoy_pct")
        fdi_abs = x.get("fdi_7m_usd_m")
        state = classify(iip, fdi_yoy)
        score = score_row(state, iip, fdi_yoy, fdi_abs)
        rows.append({
            "region": x.get("region"),
            "priority_score": score,
            "state": state,
            "iip_7m_yoy_pct": iip,
            "fdi_7m_usd_m": fdi_abs,
            "fdi_yoy_pct": fdi_yoy,
            "interpretation": interpretation(state),
            "evidence": {
                "iip_source_url": src.get("sources", {}).get("iip") if x.get("iip_source") else None,
                "fdi_source_url": src.get("sources", {}).get("fdi") if x.get("fdi_source") else None,
            },
            "next_proxies": [
                "tuyển dụng công nghiệp theo địa bàn",
                "tỷ lệ lấp đầy và giá thuê KCN/kho xưởng",
                "CAPEX/nhà máy mới và thời điểm vận hành",
                "số supplier/doanh nghiệp phụ trợ mới",
                "điện công nghiệp và vận tải hàng hóa địa phương"
            ]
        })

    rows.sort(key=lambda x: (-x["priority_score"], x["region"]))
    dual = [x["region"] for x in rows if x["state"] == "dual_acceleration"]
    divergence = [x["region"] for x in rows if x["state"] == "production_strong_capital_cooling"]
    thesis_parts = []
    if dual:
        thesis_parts.append("Gia tốc kép production + FDI đang thấy rõ nhất ở " + ", ".join(dual[:4]) + ".")
    if divergence:
        thesis_parts.append("Ngược lại, " + ", ".join(divergence[:5]) + " có sản xuất mạnh nhưng FDI mới giảm — dấu hiệu của installed-base/ramp-up hơn là câu chuyện vốn mới đơn giản.")
    thesis = " ".join(thesis_parts) or "Chưa đủ giao điểm production + capital để ưu tiên địa bàn."

    payload = {
        "meta": {
            "version": "2.2.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "regional_capital_production_divergence",
            "principle": "separate_new_capital_from_existing_capacity_ramp_up"
        },
        "thesis": thesis,
        "coverage": {
            "regions": len(rows),
            "dual_acceleration": len(dual),
            "production_strong_capital_cooling": len(divergence),
            "regions_with_both_iip_and_fdi": sum(1 for x in rows if x["iip_7m_yoy_pct"] is not None and x["fdi_yoy_pct"] is not None)
        },
        "regions": rows,
        "guardrails": src.get("caveats", []) + [
            "Priority score ranks investigation value, not expected return.",
            "Total FDI by locality cannot be assumed to be manufacturing FDI.",
            "Regional opportunity requires local supply/demand validation before action."
        ]
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"regional v2.2 regions={len(rows)} dual={len(dual)} divergence={len(divergence)}")


if __name__ == "__main__":
    main()
