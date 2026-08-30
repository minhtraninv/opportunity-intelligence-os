#!/usr/bin/env python3
"""One-shot, privacy-bounded probe of contractor fields returned by official KQLCNT detail.

Purpose: learn whether official award-result payload already exposes business contact fields
(email/phone/website/address/contact) so Contact Resolver can prefer first-party evidence.

The probe stores field names and value types only. It does NOT publish raw values.
It refreshes at most every 30 days.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import action_intel as ai
import partner_intel as pi

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "contractor_schema_probe.json"
REFRESH_DAYS = 30
MAX_DETAILS = 4
INTEREST_TOKENS = ("email", "mail", "phone", "tel", "mobile", "website", "web", "address", "contact", "represent")


def load(path: Path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def parse_dt(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def scalar_type(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def contractor_objects(main: dict):
    found = []
    for lot in pi.as_list(main.get("lotResultDTO")):
        if not isinstance(lot, dict):
            continue
        for contractor in pi.as_list(lot.get("contractorList")):
            if isinstance(contractor, dict):
                found.append(contractor)
    return found


def main():
    now = datetime.now(timezone.utc)
    old = load(OUTPUT)
    last = parse_dt(old.get("generated_at"))
    if last and now - last <= timedelta(days=REFRESH_DAYS):
        print(f"contractor-schema-probe fresh age_days={(now-last).days}; skip")
        return

    field_counts = Counter()
    field_types: dict[str, Counter] = {}
    interesting_counts = Counter()
    details_fetched = 0
    contractor_objects_seen = 0
    errors = []
    seen_result_ids = set()

    for keyword in ("số hóa", "phần mềm", "tư vấn", "máy tính"):
        if details_fetched >= MAX_DETAILS:
            break
        try:
            rows = pi.search_result_records(keyword)
        except Exception as exc:
            errors.append(f"search {keyword}: {type(exc).__name__}: {exc}")
            continue
        for row in rows:
            if details_fetched >= MAX_DETAILS:
                break
            result_id = ai.norm(ai.first_value(row, "inputResultId"))
            if not result_id or result_id in seen_result_ids:
                continue
            seen_result_ids.add(result_id)
            try:
                detail = pi.fetch_result(result_id)
                if not detail:
                    continue
                details_fetched += 1
                for contractor in contractor_objects(detail):
                    contractor_objects_seen += 1
                    for key, value in contractor.items():
                        key_text = str(key)
                        field_counts[key_text] += 1
                        field_types.setdefault(key_text, Counter())[scalar_type(value)] += 1
                        low = key_text.lower()
                        if any(token in low for token in INTEREST_TOKENS):
                            interesting_counts[key_text] += 1
            except Exception as exc:
                errors.append(f"detail {result_id}: {type(exc).__name__}: {exc}")

    fields = []
    for name, count in field_counts.most_common():
        fields.append({
            "field": name,
            "observed_in_objects": count,
            "types": dict(field_types.get(name, {})),
            "contact_like_name": any(token in name.lower() for token in INTEREST_TOKENS),
        })

    payload = {
        "schema_version": 1,
        "generated_at": now.isoformat(),
        "source": "official_msc_kqlcnt_detail",
        "privacy_rule": "field_names_and_types_only_no_raw_contact_values",
        "details_fetched": details_fetched,
        "contractor_objects_seen": contractor_objects_seen,
        "contact_like_fields": [
            {"field": name, "observed_in_objects": count}
            for name, count in interesting_counts.most_common()
        ],
        "all_fields": fields,
        "errors": errors,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"contractor-schema-probe details={details_fetched} contractors={contractor_objects_seen} "
        f"contact_like={len(interesting_counts)} errors={len(errors)}"
    )


if __name__ == "__main__":
    main()
