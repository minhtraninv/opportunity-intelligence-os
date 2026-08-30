#!/usr/bin/env python3
"""Incrementally deepen official KQLCNT history without re-fetching the same awards.

The live partner collector focuses on recent results. This backfill worker walks older
search pages over successive scheduled runs, prioritizes unseen inputResultIds, fetches
a bounded number of result details, and merges winner observations into partner history.

It is intentionally rate-bounded because MSC endpoints are website APIs, not a promised
bulk developer API.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import action_intel as ai
import partner_intel as pi

ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = ROOT / "data" / "partner_history.json"
STATE_PATH = ROOT / "data" / "partner_backfill_state.json"

PAGE_SIZE = 12
PAGES_PER_RUN = 2
MAX_PAGE = 24
MAX_DETAIL_REQUESTS = 24
DETAIL_DELAY_SECONDS = 0.15


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def search_payload(keyword: str, page_number: int):
    return [{
        "pageSize": PAGE_SIZE,
        "pageNumber": page_number,
        "query": [{
            "index": "es-contractor-selection",
            "keyWord": keyword,
            "matchType": "exact",
            "matchFields": ["notifyNo", "bidName"],
            "filters": [{
                "fieldName": "type",
                "searchType": "in",
                "fieldValues": ["es-notify-contractor"],
            }],
        }],
    }]


def search_page(keyword: str, page_number: int):
    root = ai.post_json(ai.SEARCH_URL, search_payload(keyword, page_number))
    rows, seen = [], set()
    for obj in ai.walk_objects(root):
        if not isinstance(obj, dict) or not pi.is_result_record(obj):
            continue
        notify_no = ai.norm(ai.first_value(obj, "notifyNo"))
        input_result_id = ai.norm(ai.first_value(obj, "inputResultId"))
        title = ai.norm(ai.first_value(obj, "bidName"))
        if not notify_no or not input_result_id or not title:
            continue
        key = (notify_no, input_result_id)
        if key in seen:
            continue
        seen.add(key)
        copy = dict(obj)
        copy["_search_keyword"] = keyword
        copy["_backfill_page"] = page_number
        rows.append(copy)
    return rows[:PAGE_SIZE]


def known_input_result_ids(history: dict):
    return {
        ai.norm(item.get("input_result_id"))
        for item in history.get("items", [])
        if ai.norm(item.get("input_result_id"))
    }


def merge_search_rows(rows: list[dict]):
    dedup = {}
    for row in rows:
        key = ai.norm(ai.first_value(row, "inputResultId"))
        if not key:
            continue
        if key not in dedup:
            row["_matched_keywords"] = [row.get("_search_keyword")]
            dedup[key] = row
            continue
        previous = dedup[key]
        kws = set(previous.get("_matched_keywords", []))
        if row.get("_search_keyword"):
            kws.add(row.get("_search_keyword"))
        previous["_matched_keywords"] = sorted(kws)
    return list(dedup.values())


def balanced_unseen(rows: list[dict], known: set[str]):
    unseen = [r for r in rows if ai.norm(ai.first_value(r, "inputResultId")) not in known]
    by_keyword = {keyword: [] for keyword in ai.SEARCH_KEYWORDS}
    for row in unseen:
        keyword = row.get("_search_keyword")
        if keyword in by_keyword:
            by_keyword[keyword].append(row)

    selected, used = [], set()
    while len(selected) < MAX_DETAIL_REQUESTS:
        progressed = False
        for keyword in ai.SEARCH_KEYWORDS:
            queue = by_keyword[keyword]
            while queue:
                row = queue.pop(0)
                rid = ai.norm(ai.first_value(row, "inputResultId"))
                if not rid or rid in used:
                    continue
                selected.append(row)
                used.add(rid)
                progressed = True
                break
            if len(selected) >= MAX_DETAIL_REQUESTS:
                break
        if not progressed:
            break
    return selected


def main():
    captured = ai.now_utc()
    history = load_json(HISTORY_PATH, {"version": 1, "items": []})
    state = load_json(STATE_PATH, {"version": 1, "next_page": 1, "runs": 0})
    known = known_input_result_ids(history)

    start_page = int(state.get("next_page", 1) or 1)
    if start_page < 1 or start_page > MAX_PAGE:
        start_page = 1
    pages = [p for p in range(start_page, min(MAX_PAGE, start_page + PAGES_PER_RUN - 1) + 1)]

    raw, health, errors = [], [], []
    for keyword in ai.SEARCH_KEYWORDS:
        total = 0
        for page in pages:
            try:
                rows = search_page(keyword, page)
                raw.extend(rows)
                total += len(rows)
            except Exception as exc:
                errors.append(f"backfill {keyword} page {page}: {type(exc).__name__}: {exc}")
        health.append({"keyword": keyword, "pages": pages, "result_records": total})

    candidates = balanced_unseen(merge_search_rows(raw), known)
    fresh_events = []
    fetched = 0
    detail_errors = []
    for row in candidates:
        rid = ai.norm(ai.first_value(row, "inputResultId"))
        if not rid:
            continue
        try:
            main_result = pi.fetch_result(rid)
            fetched += 1
            if main_result:
                events = pi.winner_events(row, main_result, captured)
                for event in events:
                    event["collection_mode"] = "historical_backfill"
                    event["backfill_page"] = row.get("_backfill_page")
                    event["matched_keywords"] = row.get("_matched_keywords", [row.get("_search_keyword")])
                fresh_events.extend(events)
        except Exception as exc:
            detail_errors.append(f"KQLCNT {rid}: {type(exc).__name__}: {exc}")
        time.sleep(DETAIL_DELAY_SECONDS)

    history = pi.merge_history(history, fresh_events, captured)
    write_json(HISTORY_PATH, history)

    next_page = start_page + PAGES_PER_RUN
    if next_page > MAX_PAGE:
        next_page = 1
    new_state = {
        "version": 1,
        "updated_at": ai.iso(captured),
        "runs": int(state.get("runs", 0) or 0) + 1,
        "last_pages": pages,
        "next_page": next_page,
        "max_page": MAX_PAGE,
        "page_size": PAGE_SIZE,
        "detail_budget_per_run": MAX_DETAIL_REQUESTS,
        "known_input_result_ids_before_run": len(known),
        "unseen_candidates_found": len(candidates),
        "details_fetched": fetched,
        "winner_events_added_or_refreshed": len(fresh_events),
        "history_events_after_run": len(history.get("items", [])),
        "search_errors": errors,
        "detail_errors": detail_errors,
        "source_health": health,
        "principle": "bounded_incremental_backfill_of_official_award_results",
    }
    write_json(STATE_PATH, new_state)

    print(
        "partner-backfill "
        f"pages={pages} known_before={len(known)} unseen={len(candidates)} fetched={fetched} "
        f"winner_events={len(fresh_events)} history={len(history.get('items', []))} "
        f"errors={len(errors) + len(detail_errors)} next_page={next_page}"
    )
    for error in (errors + detail_errors)[:20]:
        print(error)


if __name__ == "__main__":
    main()
