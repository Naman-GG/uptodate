"""Lever postings API.

GET https://api.lever.co/v0/postings/{company}?mode=json
Keyless. Returns a bare JSON array. Descriptions arrive pre-flattened as
`descriptionPlain`; `additionalPlain` holds the requirements/EEO tail.
"""
from __future__ import annotations

from datetime import datetime, timezone

from common.http import get_json
from common.posting import RawPosting, clean_location

ENDPOINT = "https://api.lever.co/v0/postings/{token}?mode=json"


def fetch(token: str) -> list[RawPosting]:
    payload = get_json(ENDPOINT.format(token=token))
    if not isinstance(payload, list):
        return []
    return [p for p in (_parse(token, job) for job in payload) if p]


def _parse(token: str, job: dict) -> RawPosting | None:
    native_id = job.get("id")
    if not native_id:
        return None

    categories = job.get("categories") or {}
    locations = clean_location(categories.get("allLocations")) or clean_location(
        categories.get("location")
    )
    # Lever exposes an explicit ISO country code on some boards - keep it as a
    # location token so the extractor sees it even when the office string is vague.
    country = job.get("country")
    if country and not locations:
        locations = [country]

    body = "\n\n".join(
        part for part in (job.get("descriptionPlain"), job.get("additionalPlain")) if part
    )

    return RawPosting(
        posting_id=f"lever#{token}#{native_id}",
        source="lever",
        company_token=token,
        company=token.replace("-", " ").title(),
        title=(job.get("text") or "").strip(),
        locations=locations,
        description=body.strip(),
        apply_url=job.get("hostedUrl") or job.get("applyUrl") or "",
        posted_at=_ms_to_iso(job.get("createdAt")),
        department=categories.get("department") or categories.get("team"),
        employment_type=categories.get("commitment"),
        remote_hint=job.get("workplaceType"),
    )


def _ms_to_iso(value) -> str | None:
    if not isinstance(value, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat(timespec="seconds")
    except (ValueError, OSError, OverflowError):
        return None
