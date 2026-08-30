#!/usr/bin/env python3
"""Corporate Action Intelligence from official HNX public disclosures.

A disclosure title is only an investigation trigger. Routine market-status notices and
registration formalities are ignored unless the title contains evidence of capital
deployment, financing, a contract, acquisition, or an operating project.
"""
from __future__ import annotations

import hashlib
import json
import re
import ssl
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import certifi
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "corporate_intelligence.json"
HISTORY = ROOT / "data" / "corporate_history.json"
HNX_CA_BUNDLE = ROOT / "pipeline" / "certs" / "globalsign_hnx_intermediates.pem"
VN_TZ = timezone(timedelta(hours=7))
UA = "Mozilla/5.0 (compatible; OpportunityIntelligenceOS/3.0; +https://github.com/minhtraninv/opportunity-intelligence-os)"

SOURCES = [
    {
        "id": "hnx-listed",
        "name": "HNX - công bố niêm yết",
        "url": "https://hnx.vn/vi-vn/thong-tin-cong-bo-ny-hnx.html",
        "authority": 1.0,
    },
    {
        "id": "hnx-upcom",
        "name": "HNX - công bố UPCoM",
        "url": "https://hnx.vn/vi-vn/thong-tin-cong-bo-up-hnx.html",
        "authority": 1.0,
    },
]

RULES = (
    ("contract_award", (
        "trúng thầu", "trúng gói thầu", "ký hợp đồng", "ký kết hợp đồng",
        "hợp đồng epc", "hợp đồng xây dựng", "hợp đồng cung cấp",
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
    "capex_project": ["nhà thầu phụ", "facility/cleaning", "PPE & vật tư", "logistics", "tuyển dụng", "IT/office setup"],
    "contract_award": ["nhà thầu phụ", "vật tư", "logistics", "nhân công", "bảo trì"],
    "capital_raise": ["theo dõi mục đích sử dụng vốn", "xác minh dự án nhận vốn", "tìm trigger triển khai tiếp theo"],
    "acquisition_investment": ["dịch vụ tích hợp vận hành", "IT/kế toán", "branding/website", "tuyển dụng", "facility"],
    "financing": ["theo dõi CAPEX hoặc mua sắm sau giải ngân", "không coi vay vốn tự thân là nhu cầu mua"],
}


class VerifiedHnxAdapter(HTTPAdapter):
    """Keep TLS verification enabled while supplying HNX's omitted intermediates."""

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        context = ssl.create_default_context(cafile=certifi.where())
        if HNX_CA_BUNDLE.exists():
            context.load_verify_locations(cafile=str(HNX_CA_BUNDLE))
        pool_kwargs["ssl_context"] = context
        return super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)


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
    session.mount("https://", VerifiedHnxAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.headers.update({
        "User-Agent": UA,
        "Accept-Language": "vi-VN,vi;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
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
            int(match.group(3)),
            int(match.group(2)),
            int(match.group(1)),
            int(match.group(4)),
            int(match.group(5)),
            tzinfo=VN_TZ,
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

        published_at = parse_dt(values[1]) if len(values) > 1 else None
        ticker = values[2].upper() if len(values) > 2 else ""
        title = values[3] if len(values) > 3 else ""

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
            "ticker": ticker,
            "title": title,
            "event_type": event_type,
            "published_at": iso(published_at),
            "captured_at": iso(captured_at),
            "source_id": src["id"],
            "publisher": src["name"],
            "source_url": source_url,
            "authority": src["authority"],
            "likely_downstream_needs_hypothesis": LIKELY_NEEDS.get(event_type, []),
            "interpretation_rule": "disclosure_trigger_not_investment_recommendation",
        })

    return output, None


def main() -> None:
    now = now_utc()
    all_events = []
    health = []

    for src in SOURCES:
        rows, error = parse_source(src, now)
        all_events.extend(rows)
        health.append({
            "source_id": src["id"],
            "source_name": src["name"],
            "status": "error" if error else "ok",
            "items_this_run": len(rows),
            "error": error,
        })

    history = load_json(HISTORY, {"events": []})
    existing = {
        x.get("id"): x
        for x in history.get("events", [])
        if isinstance(x, dict) and x.get("id")
    }
    for event in all_events:
        existing[event["id"]] = event

    history_rows = sorted(
        existing.values(),
        key=lambda x: x.get("published_at") or "",
        reverse=True,
    )[:2500]
    write_json(HISTORY, {"updated_at": now.isoformat(), "events": history_rows})

    cutoff = now - timedelta(days=45)
    recent = []
    for event in history_rows:
        try:
            if datetime.fromisoformat(str(event.get("published_at", "")).replace("Z", "+00:00")) >= cutoff:
                recent.append(event)
        except Exception:
            pass

    counts = {}
    for event in recent:
        counts[event["event_type"]] = counts.get(event["event_type"], 0) + 1

    payload = {
        "meta": {
            "version": "3.0.0",
            "generated_at": now.isoformat(),
            "mode": "official_corporate_action_discovery",
            "principle": "corporate_disclosure_is_an_execution_trigger_not_a_buy_signal",
        },
        "coverage": {
            "sources": len(SOURCES),
            "healthy_sources": sum(1 for x in health if x["status"] == "ok"),
            "source_errors": sum(1 for x in health if x["status"] == "error"),
            "events_this_run": len(all_events),
            "historical_events": len(history_rows),
            "recent_events_45d": len(recent),
            "event_types_45d": counts,
        },
        "source_health": health,
        "recent_events": recent[:120],
        "reading_rule": (
            "Một disclosure chỉ mở hồ sơ điều tra. Cần đọc tài liệu gốc, quy mô, thời điểm, "
            "funding, execution và phản chứng trước khi nối thành thesis."
        ),
    }
    write_json(OUT, payload)
    print(
        f"corporate sources={len(SOURCES)} healthy={payload['coverage']['healthy_sources']} "
        f"run={len(all_events)} history={len(history_rows)} recent={len(recent)}"
    )


if __name__ == "__main__":
    main()
