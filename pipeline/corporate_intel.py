#!/usr/bin/env python3
from __future__ import annotations

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

SOURCES = [
    {"id":"hnx-listed","name":"HNX - công bố niêm yết","url":"https://hnx.vn/vi-vn/thong-tin-cong-bo-ny-hnx.html","authority":1.0},
    {"id":"hnx-upcom","name":"HNX - công bố UPCoM","url":"https://forum.hnx.vn/vi-vn/thong-tin-cong-bo-up-hnx.html","authority":1.0},
]

RULES = (
    ("capex_project", ("dự án", "nhà máy", "mở rộng", "xây dựng", "đầu tư dự án", "tăng công suất")),
    ("contract_award", ("trúng thầu", "hợp đồng", "ký kết", "ký hợp đồng")),
    ("capital_raise", ("tăng vốn", "phát hành cổ phiếu", "chào bán", "phát hành trái phiếu", "đăng ký giao dịch bổ sung", "thay đổi đăng ký giao dịch")),
    ("acquisition_investment", ("góp vốn", "mua cổ phần", "chuyển nhượng", "mua lại", "thành lập công ty con", "công ty con")),
    ("financing", ("vay vốn", "hạn mức tín dụng", "tài sản bảo đảm", "thế chấp")),
)

NEGATIVE = ("cảnh báo", "kiểm soát", "không được phép giao dịch ký quỹ", "sở hữu của nhà đầu tư nước ngoài", "hủy niêm yết", "ngừng giao dịch")

LIKELY_NEEDS = {
    "capex_project": ["nhà thầu phụ", "facility/cleaning", "PPE & vật tư", "logistics", "tuyển dụng", "IT/office setup"],
    "contract_award": ["nhà thầu phụ", "vật tư", "logistics", "nhân công", "bảo trì"],
    "capital_raise": ["theo dõi mục đích sử dụng vốn", "xác minh dự án nhận vốn", "tìm procurement/facility trigger tiếp theo"],
    "acquisition_investment": ["dịch vụ tích hợp vận hành", "IT/kế toán", "branding/website", "tuyển dụng", "facility"],
    "financing": ["theo dõi CAPEX hoặc mua sắm sau giải ngân", "không coi vay vốn tự thân là nhu cầu mua"],
}


def session():
    retry = Retry(total=2, connect=2, read=2, status=2, backoff_factor=0.8,
                  status_forcelist=(429,500,502,503,504), allowed_methods=frozenset({"GET"}), raise_on_status=False)
    s=requests.Session(); a=HTTPAdapter(max_retries=retry); s.mount("https://",a); s.mount("http://",a)
    s.headers.update({"User-Agent":UA,"Accept-Language":"vi-VN,vi;q=0.9"}); return s

S=session()

def norm(x): return re.sub(r"\s+"," ",x or "").strip()
def iso(dt): return dt.astimezone(timezone.utc).isoformat()
def now(): return datetime.now(timezone.utc)

def parse_dt(text):
    m=re.search(r"(\d{1,2})/(\d{1,2})/(20\d{2})\s+(\d{1,2}):(\d{2})", text or "")
    if not m: return None
    try: return datetime(int(m.group(3)),int(m.group(2)),int(m.group(1)),int(m.group(4)),int(m.group(5)),tzinfo=VN_TZ).astimezone(timezone.utc)
    except ValueError: return None

def load(path, default):
    try: return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception: return default

def write(path, payload): path.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")

def classify(title):
    t=title.casefold()
    if any(x in t for x in NEGATIVE): return None
    for kind, phrases in RULES:
        if any(p.casefold() in t for p in phrases): return kind
    return None

def parse_source(src, captured):
    try:
        r=S.get(src["url"],timeout=(10,30)); r.raise_for_status()
    except Exception as exc:
        return [], f"{src['name']}: {type(exc).__name__}: {exc}"
    soup=BeautifulSoup(r.text,"html.parser")
    out=[]; seen=set()
    for tr in soup.find_all("tr"):
        cells=tr.find_all("td")
        if len(cells)<3: continue
        row=[norm(c.get_text(" ",strip=True)) for c in cells]
        date=next((parse_dt(x) for x in row if parse_dt(x)),None)
        if not date: continue
        ticker=next((x for x in row if re.fullmatch(r"[A-Z0-9]{2,12}",x or "") and not x.isdigit()),"")
        title=max(row,key=len) if row else ""
        kind=classify(title)
        if not kind: continue
        key=f"{src['id']}|{ticker}|{title.casefold()}"
        if key in seen: continue
        seen.add(key)
        anchor=tr.find("a",href=True)
        url=urljoin(src["url"],anchor["href"]) if anchor else src["url"]
        out.append({
            "id": re.sub(r"[^a-zA-Z0-9]","",f"{src['id']}{ticker}{abs(hash(title))}")[:40],
            "source_id":src["id"],"source_name":src["name"],"source_url":url,"authority":src["authority"],
            "ticker":ticker or "HNX","title":title,"event_type":kind,"published_at":iso(date),
            "first_seen_at":iso(captured),"last_seen_at":iso(captured),
        })
    return out[:80], None

def merge(old, fresh, captured):
    by={(x.get("source_id"),x.get("ticker"),x.get("title")):dict(x) for x in old.get("items",[]) if x.get("title")}
    for x in fresh:
        k=(x.get("source_id"),x.get("ticker"),x.get("title")); prev=by.get(k)
        if prev:
            by[k]={**prev,**x,"first_seen_at":prev.get("first_seen_at") or x["first_seen_at"],"last_seen_at":iso(captured)}
        else: by[k]=x
    items=list(by.values()); items.sort(key=lambda x:x.get("published_at") or "", reverse=True)
    return {"version":1,"updated_at":iso(captured),"items":items[:1500]}

def score(x,captured):
    base={"capex_project":88,"contract_award":86,"acquisition_investment":72,"capital_raise":58,"financing":45}.get(x["event_type"],40)
    try: age=(captured-datetime.fromisoformat(x["published_at"])).total_seconds()/86400
    except Exception: age=30
    freshness=max(0,20-min(20,age*1.5))
    score=min(95,round(base*0.78+freshness))
    if x["event_type"] in {"capex_project","contract_award"} and score>=72: level="investigate_now"
    elif score>=60: level="watch"
    else: level="context"
    return {**x,"buyer_trigger_score":score,"action_level":level,"likely_needs":LIKELY_NEEDS[x["event_type"]],
            "next_action":"Mở công bố gốc, xác định doanh nghiệp/dự án cụ thể, kiểm tra mục đích vốn hoặc phạm vi hợp đồng; chỉ sau đó mới tìm buyer role và nhà cung cấp phụ trợ.",
            "kill_criteria":"Loại nếu công bố chỉ mang tính thủ tục chứng khoán, không tạo CAPEX/hợp đồng/nhu cầu vận hành cụ thể, hoặc không xác định được buyer thực."}

def main():
    captured=now(); fresh=[]; errors=[]; health=[]
    for src in SOURCES:
        items,err=parse_source(src,captured); fresh.extend(items)
        health.append({"source_id":src["id"],"name":src["name"],"items_this_run":len(items),"status":"error" if err else "ok","error":err})
        if err: errors.append(err)
    history=merge(load(HISTORY,{"version":1,"items":[]}),fresh,captured); write(HISTORY,history)
    scored=[score(x,captured) for x in history["items"]]
    recent=[x for x in scored if (captured-datetime.fromisoformat(x["published_at"])).days<=30]
    recent.sort(key=lambda x:(x["buyer_trigger_score"],x["published_at"]),reverse=True)
    output={"meta":{"version":"1.3","generated_at":iso(captured),"mode":"corporate_action_intelligence"},
            "coverage":{"historical_events":len(history["items"]),"recent_events":len(recent),"investigate_now":sum(x["action_level"]=="investigate_now" for x in recent),"source_errors_last_run":len(errors)},
            "source_health":health,"buyer_triggers":recent[:60],
            "warnings":["HNX là nguồn công bố chính thức, nhưng tiêu đề công bố chỉ là trigger điều tra; phải đọc tài liệu gốc trước khi suy ra nhu cầu mua sắm.",*([f"Có {len(errors)} nguồn lỗi ở lần chạy gần nhất."] if errors else [])]}
    write(OUT,output)
    print(f"corporate-intel history={len(history['items'])} recent={len(recent)} investigate={output['coverage']['investigate_now']} errors={len(errors)}")

if __name__=="__main__": main()
