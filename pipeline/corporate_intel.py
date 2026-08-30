#!/usr/bin/env python3
"""Corporate Action Intelligence from official HNX public disclosures.

A disclosure title is only an investigation trigger. The system intentionally ignores
routine market-status notices and securities-registration formalities unless the title
contains evidence of real capital deployment, financing, a contract, acquisition, or
an operating project.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "corporate_intelligence.json"
HISTORY = ROOT / "data" / "corporate_history.json"
VN_TZ = timezone(timedelta(hours=7))
UA = "Mozilla/5.0 (compatible; OpportunityIntelligenceOS/1.3; +https://github.com/)"

# Alternate official HNX subdomains are used because the apex HNX certificate chain
# is not consistently accepted by GitHub-hosted Ubuntu runners.
SOURCES = [
    {
        "id": "hnx-listed",
        "name": "HNX - công bố niêm yết",
        "url": "https://portal.hnx.vn/vi-vn/thong-tin-cong-bo-ny-hnx.html",
        "authority": 1.0,
    },
    {
        "id": "hnx-upcom",
        "name": "HNX - công bố UPCoM",
        "url": "https://tttt.hnx.vn/vi-vn/thong-tin-cong-bo-up-hnx.html",
        "authority": 1.0,
    },
]

RULES = (
    ("contract_award", (
        "trúng thầu", "trúng gói thầu", "ký hợp đồng", "ký kết hợp đồng",
        "hợp đồng EPC", "hợp đồng xây dựng", "hợp đồng cung cấp",
    )),
    ("capex_project", (
        "khởi công dự án", "triển khai dự án", "đầu tư dự án", "phê duyệt dự án",
        "mở rộng nhà máy", "xây dựng nhà máy", "nhà máy mới", "tăng công suất",
        "mở rộng công suất", "trung tâm dữ liệu", "khu công nghiệp",
    )),
    ("capital_raise", (
        "tăng vốn điều lệ", "phát hành thêm", "phát hành cổ phiếu", "chào bán cổ phiếu",
        "chào bán riêng lẻ", "phát hành trái phiếu", "huy động vốn",
    )),
    ("acquisition_investment", (
        "góp vốn", "mua cổ phần", "nhận chuyển nhượng", "mua lại", "m&a",
        "thành lập công ty con", "thành lập công ty", "đầu tư vào công ty",
    )),
    ("financing", (
        "vay vốn", "hạn mức tín dụng", "cấp tín dụng", "khoản vay", "hợp đồng tín dụng",
    )),
)

NEGATIVE = (
    "cảnh báo", "kiểm soát", "không được phép giao dịch ký quỹ", "sở hữu của nhà đầu tư nước ngoài",
    "hủy niêm yết", "ngừng giao dịch", "đình chỉ giao dịch", "ngày giao dịch đầu tiên",
    "đăng ký giao dịch bổ sung", "thay đổi đăng ký giao dịch", "chấp thuận đăng ký giao dịch",
    "thông báo trạng thái chứng khoán", "quản lý sở hữu",
)

LIKELY_NEEDS = {
    "capex_project": [
        "nhà thầu phụ", "facility/cleaning", "PPE & vật tư", "logistics",
        "tuyển dụng", "IT/office setup",
    ],
    "contract_award": ["nhà thầu phụ", "vật tư", "logistics", "nhân công", "bảo trì"],
    "capital_raise": [
        "theo dõi mục đích sử dụng vốn", "xác minh dự án nhận vốn",
        "tìm procurement/facility trigger tiếp theo",
    ],
    "acquisition_investment": [
        "dịch vụ tích hợp vận hành", "IT/kế toán", "branding/website", "tuyển dụng", "facility",
    ],
    "financing": [
        "theo dõi CAPEX hoặc mua sắm sau giải ngân",
        "không coi vay vốn tự thân là nhu cầu mua",
    ],
}


def build_session() -> requests.Session:
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        status=2,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": UA, "Accept-Language": "vi-VN,vi;q=0.9"})
    return session


SESSION = build_session()


def norm(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(text: str) -> datetime | None:
    match = re.search(r"(\d{1,2})/(\d{1,2})/(20\d{2})\s+(\d{1,2}):(\d{2})", text or "")
    if not match:
        return None
    try:
        return datetime(
            int(match.group(3)), int(match.group(2)), int(match.group(1)),
            int(match.group(4)), int(match.group(5)), tzinfo=VN_TZ,
        ).astimezone(timezone.utc)
    except ValueError:
        return None


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def event_id(source_id: str, ticker: str, title: str) -> str:
    raw = f"{source_id}|{ticker}|{norm(title).casefold()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def classify(title: str) -> str | None:
    lowered = norm(title).casefold()
    if any(marker.casefold() in lowered for marker in NEGATIVE):
        return None
    for event_type, phrases in RULES:
        if any(phrase.casefold() in lowered for phrase in phrases):
            return event_type
    return None


def parse_source(src: dict, captured_at: datetime) -> tuple[list[dict], str | None]:
    try:
        response = SESSION.get(src["url"], timeout=(10, 30))
        response.raise_for_status()
    except Exception as exc:
        return [], f"{src['name']}: {type(exc).__name__}: {exc}"

    soup = BeautifulSoup(response.text, "html.parser")
    output = []
    seen = set()

    for tr in soup.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 4:
            continue

        values = [norm(cell.get_text(" ", strip=True)) for cell in cells]

        # HNX disclosure table is normally STT | date | ticker | title | attachment.
        published_at = parse_dt(values[1]) if len(values) > 1 else None
        ticker = values[2].upper() if len(values) > 2 else ""
        title = values[3] if len(values) > 3 else ""

        # Fallback for mirrors whose markup contains an extra leading column.
        if not published_at:
            date_index = next((i for i, value in enumerate(values) if parse_dt(value)), None)
            if date_index is None:
                continue
            published_at = parse_dt(values[date_index])
            ticker = values[date_index + 1].upper() if len(values) > date_index + 1 else ""
            title = values[date_index + 2] if len(values) > date_index + 2 else ""

        if not published_at or not re.fullmatch(r"[A-Z0-9]{2,12}", ticker or ""):
            continue
        if ticker == "HNX" or len(title) < 12:
            continue

        event_type = classify(title)
        if not event_type:
            continue

        key = event_id(src["id"], ticker, title)
        if key in seen:
            continue
        seen.add(key)

        title_cell = cells[3] if len(cells) > 3 else tr
        anchor = title_cell.find("a", href=True) or tr.find("a", href=True)
        source_url = urljoin(src["url"], anchor["href"]) if anchor else src["url"]

        output.append({
            "id": key,
            "source_id": src["id"],
            "source_name": src["name"],
            "source_url": source_url,
            "authority": src["authority"],
            "ticker": ticker,
            "title": title,
            "event_type": event_type,
            "published_at": iso(published_at),
            "first_seen_at": iso(captured_at),
            "last_seen_at": iso(captured_at),
        })

    return output[:80], None


def merge_history(old: dict, fresh: list[dict], captured_at: datetime) -> dict:
    merged = {
        (item.get("source_id"), item.get("ticker"), item.get("title")): dict(item)
        for item in old.get("items", [])
        if item.get("title")
    }

    for item in fresh:
        key = (item.get("source_id"), item.get("ticker"), item.get("title"))
        previous = merged.get(key)
        if previous:
            merged[key] = {
                **previous,
                **item,
                "id": event_id(item["source_id"], item["ticker"], item["title"]),
                "first_seen_at": previous.get("first_seen_at") or item["first_seen_at"],
                "last_seen_at": iso(captured_at),
            }
        else:
            merged[key] = item

    items = list(merged.values())
    items.sort(key=lambda x: x.get("published_at") or "", reverse=True)
    return {"version": 2, "updated_at": iso(captured_at), "items": items[:1500]}


def score_trigger(item: dict, captured_at: datetime) -> dict:
    base = {
        "capex_project": 88,
        "contract_award": 86,
        "acquisition_investment": 72,
        "capital_raise": 58,
        "financing": 45,
    }.get(item["event_type"], 40)

    try:
        age_days = (captured_at - datetime.fromisoformat(item["published_at"])).total_seconds() / 86400
    except Exception:
        age_days = 30

    freshness = max(0, 20 - min(20, age_days * 1.5))
    score = min(95, round(base * 0.78 + freshness))

    if item["event_type"] in {"capex_project", "contract_award"} and score >= 72:
        action_level = "investigate_now"
    elif score >= 60:
        action_level = "watch"
    else:
        action_level = "context"

    return {
        **item,
        "buyer_trigger_score": score,
        "action_level": action_level,
        "likely_needs": LIKELY_NEEDS[item["event_type"]],
        "next_action": (
            "Mở công bố gốc và tài liệu đính kèm; xác định dự án/hợp đồng/mục đích vốn cụ thể. "
            "Chỉ sau khi xác nhận có hoạt động kinh tế thực mới tìm buyer role và nhà cung cấp phụ trợ."
        ),
        "kill_criteria": (
            "Loại nếu công bố chỉ là thủ tục chứng khoán, không dẫn tới CAPEX/hợp đồng/nhu cầu vận hành, "
            "hoặc không xác định được doanh nghiệp và hoạt động tạo nhu cầu thực."
        ),
    }


def main() -> None:
    captured_at = now_utc()
    fresh = []
    errors = []
    source_health = []

    for src in SOURCES:
        items, error = parse_source(src, captured_at)
        fresh.extend(items)
        source_health.append({
            "source_id": src["id"],
            "name": src["name"],
            "items_this_run": len(items),
            "status": "error" if error else "ok",
            "error": error,
        })
        if error:
            errors.append(error)

    history = merge_history(
        load_json(HISTORY, {"version": 2, "items": []}),
        fresh,
        captured_at,
    )
    write_json(HISTORY, history)

    scored = [score_trigger(item, captured_at) for item in history["items"]]
    recent = []
    for item in scored:
        try:
            published_at = datetime.fromisoformat(item["published_at"])
        except Exception:
            continue
        if (captured_at - published_at).total_seconds() <= 30 * 86400:
            recent.append(item)

    recent.sort(
        key=lambda x: (x["buyer_trigger_score"], x["published_at"]),
        reverse=True,
    )

    output = {
        "meta": {
            "version": "1.3",
            "generated_at": iso(captured_at),
            "mode": "corporate_action_intelligence",
            "principle": "official_disclosure_then_document_verification",
        },
        "coverage": {
            "historical_events": len(history["items"]),
            "recent_events": len(recent),
            "investigate_now": sum(item["action_level"] == "investigate_now" for item in recent),
            "source_errors_last_run": len(errors),
        },
        "source_health": source_health,
        "buyer_triggers": recent[:60],
        "warnings": [
            "HNX là nguồn công bố chính thức, nhưng tiêu đề chỉ là trigger điều tra; phải đọc tài liệu gốc trước khi suy ra nhu cầu mua sắm.",
            "Capital raise/financing không tự động đồng nghĩa với cơ hội bán hàng; cần bằng chứng vốn được dùng cho hoạt động tạo nhu cầu.",
            *([f"Có {len(errors)} nguồn lỗi ở lần chạy gần nhất."] if errors else []),
        ],
    }
    write_json(OUT, output)

    print(
        f"corporate-intel history={len(history['items'])} recent={len(recent)} "
        f"investigate={output['coverage']['investigate_now']} errors={len(errors)}"
    )
    for error in errors:
        print(error)


if __name__ == "__main__":
    main()
