#!/usr/bin/env python3
"""V1.5.3 Extract only role/generic business emails from official MSC KQLCNT.

Privacy / precision boundary:
- whitelist only recEmail;
- require exact contractor orgCode/taxCode match;
- require an organization-like contractor name;
- surface only role/generic mailbox patterns by default;
- never read/publish repIdNo or other personal identifiers;
- historical award contact is a public contact path, not evidence of current bidding.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import action_intel as ai
import partner_intel as pi

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PARTNER_HISTORY_PATH = DATA / "partner_history.json"
PARTNER_INTEL_PATH = DATA / "partner_intelligence.json"
OUTPUT_PATH = DATA / "official_contact_intelligence.json"
MAX_DETAILS = 30
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
ORG_MARKERS = (
    "công ty", "tổng công ty", "tập đoàn", "hợp tác xã", "doanh nghiệp",
    "liên danh", "trung tâm", "xí nghiệp", "chi nhánh", "viện",
)
ROLE_MAIL_TOKENS = (
    "info", "contact", "sales", "sale", "kinhdoanh", "business", "biz",
    "duan", "project", "dauthau", "duthau", "tender", "bidding", "hoso",
    "kythuat", "technical", "support", "hotro", "service", "admin", "office",
    "luutru", "togiupviec", "procurement", "sourcing", "cs", "cskh",
)


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def norm(value) -> str:
    return str(value or "").strip()


def target_partner_ids(partner_intel: dict):
    ids = set()
    for match in partner_intel.get("matches_by_open_tender", []):
        for candidate in match.get("candidates", [])[:3]:
            partner_id = norm(candidate.get("partner_id"))
            if partner_id:
                ids.add(partner_id)
    return ids


def event_partner_key(event: dict):
    return norm(event.get("contractor_code")) or norm(event.get("tax_code")) or norm(event.get("contractor_name")).casefold()


def contractor_objects(main: dict):
    for lot in pi.as_list(main.get("lotResultDTO")):
        if not isinstance(lot, dict):
            continue
        for contractor in pi.as_list(lot.get("contractorList")):
            if isinstance(contractor, dict):
                yield contractor


def contractor_matches(contractor: dict, event: dict) -> bool:
    expected_code = norm(event.get("contractor_code"))
    expected_tax = norm(event.get("tax_code"))
    actual_org = norm(ai.first_value(contractor, "orgCode"))
    actual_tax = norm(ai.first_value(contractor, "taxCode"))
    return bool(
        (expected_code and actual_org and expected_code == actual_org)
        or (expected_tax and actual_tax and expected_tax == actual_tax)
        or (expected_tax and actual_org and actual_org.endswith(expected_tax))
    )


def valid_email(value) -> str | None:
    email = norm(value).lower()
    if not email or len(email) > 254 or not EMAIL_RE.match(email):
        return None
    return email


def organization_like(name: str) -> bool:
    text = norm(name).casefold()
    return any(marker in text for marker in ORG_MARKERS)


def role_or_generic_email(email: str) -> bool:
    local = email.split("@", 1)[0].lower()
    compact = re.sub(r"[^a-z0-9]+", "", local)
    return any(token in compact for token in ROLE_MAIL_TOKENS)


def build():
    now = datetime.now(timezone.utc)
    history = load(PARTNER_HISTORY_PATH)
    partner_intel = load(PARTNER_INTEL_PATH)
    targets = target_partner_ids(partner_intel)

    events_by_partner = defaultdict(list)
    for event in history.get("items", []):
        key = event_partner_key(event)
        if key in targets and event.get("input_result_id"):
            events_by_partner[key].append(event)
    for events in events_by_partner.values():
        events.sort(key=lambda x: x.get("award_public_at") or x.get("first_seen_at") or "", reverse=True)

    contacts = {}
    errors = []
    fetched = 0
    scanned_targets = 0
    email_candidates_seen = 0
    filtered_non_org = 0
    filtered_personal_like = 0

    for partner_id in sorted(targets):
        if fetched >= MAX_DETAILS:
            break
        events = events_by_partner.get(partner_id, [])
        if not events:
            continue
        scanned_targets += 1
        for event in events[:2]:
            if fetched >= MAX_DETAILS or partner_id in contacts:
                break
            result_id = norm(event.get("input_result_id"))
            try:
                main = pi.fetch_result(result_id)
                fetched += 1
                if not main:
                    continue
                for contractor in contractor_objects(main):
                    if not contractor_matches(contractor, event):
                        continue
                    email = valid_email(ai.first_value(contractor, "recEmail"))
                    if not email:
                        continue
                    email_candidates_seen += 1
                    contractor_name = norm(event.get("contractor_name"))
                    if not organization_like(contractor_name):
                        filtered_non_org += 1
                        continue
                    if not role_or_generic_email(email):
                        filtered_personal_like += 1
                        continue
                    contacts[partner_id] = {
                        "partner_id": partner_id,
                        "contractor_name": contractor_name,
                        "contractor_code": event.get("contractor_code"),
                        "tax_code": event.get("tax_code"),
                        "contact_status": "verified_official_msc_role_mailbox",
                        "contact_paths": [{
                            "type": "email",
                            "value": email,
                            "scope": "role/generic business email công khai trong contractor object của KQLCNT",
                            "source_url": event.get("source_url"),
                            "source_type": "official_msc_kqlcnt_contractor_object",
                            "verified_at": now.isoformat(),
                            "identity_match": "exact_orgCode_or_taxCode",
                            "mailbox_class": "role_or_generic",
                        }],
                        "award_tender_code": event.get("tender_code"),
                        "award_public_at": event.get("award_public_at"),
                        "caveat": "Email role/generic được công khai trong KQLCNT lịch sử của đúng pháp nhân; không chứng minh người nhận phụ trách gói hiện tại.",
                    }
                    break
            except Exception as exc:
                errors.append(f"{partner_id} {result_id}: {type(exc).__name__}: {exc}")

    return {
        "meta": {
            "version": "1.5.3",
            "generated_at": now.isoformat(),
            "mode": "official_msc_role_contact_intelligence",
            "privacy_rule": "whitelist_recEmail_exact_entity_match_organization_only_role_or_generic_mailbox_no_personal_identifiers",
        },
        "coverage": {
            "target_partner_ids": len(targets),
            "targets_with_history": len(events_by_partner),
            "targets_scanned": scanned_targets,
            "details_fetched": fetched,
            "email_candidates_seen": email_candidates_seen,
            "verified_contact_entities": len(contacts),
            "verified_contact_paths": sum(len(x.get("contact_paths", [])) for x in contacts.values()),
            "filtered_non_organization": filtered_non_org,
            "filtered_personal_like_mailboxes": filtered_personal_like,
            "errors": len(errors),
        },
        "contacts": list(contacts.values()),
        "errors": errors,
        "warnings": [
            "recEmail là contact công khai trong KQLCNT lịch sử, không phải bằng chứng bidder hiện tại.",
            "Email có dạng cá nhân không được surface mặc định dù xuất hiện trong nguồn công khai.",
            "Không thu thập repIdNo hoặc trường định danh cá nhân.",
        ],
    }


def main():
    payload = build()
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    c = payload["coverage"]
    print(
        "official-contact-intel "
        f"targets={c['target_partner_ids']} scanned={c['targets_scanned']} candidates={c['email_candidates_seen']} "
        f"verified={c['verified_contact_entities']} filtered_personal={c['filtered_personal_like_mailboxes']} "
        f"filtered_non_org={c['filtered_non_organization']} errors={c['errors']}"
    )


if __name__ == "__main__":
    main()
