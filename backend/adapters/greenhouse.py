"""Greenhouse job board API.

GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
Keyless. `content` arrives HTML-escaped, so it needs a double unescape.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from common.http import get_json
from common.posting import RawPosting, clean_location
from common.text import html_to_text

ENDPOINT = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"


def fetch(token: str) -> list[RawPosting]:
    payload = get_json(ENDPOINT.format(token=token))
    jobs = payload.get("jobs") or []
    return [p for p in (_parse(token, job) for job in jobs) if p]


def _parse(token: str, job: dict) -> RawPosting | None:
    native_id = job.get("id")
    if not native_id:
        return None

    offices = [o.get("name") for o in (job.get("offices") or []) if isinstance(o, dict)]
    locations = clean_location(job.get("location")) or clean_location(offices)

    departments = [d.get("name") for d in (job.get("departments") or []) if isinstance(d, dict)]

    return RawPosting(
        posting_id=f"greenhouse#{token}#{native_id}",
        source="greenhouse",
        company_token=token,
        company=_company_name(job, token),
        title=(job.get("title") or "").strip(),
        locations=locations,
        description=html_to_text(job.get("content")),
        apply_url=job.get("absolute_url") or "",
        posted_at=_iso(job.get("first_published") or job.get("updated_at")),
        department=departments[0] if departments else None,
    )


def _company_name(job: dict, token: str) -> str:
    """Greenhouse often returns "Acme Job Board" as company_name; trim the suffix."""
    raw = (job.get("company_name") or "").strip()
    raw = re.sub(r"\s+(job board|careers|jobs)$", "", raw, flags=re.I).strip()
    return raw or token.replace("-", " ").title()


def _iso(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).astimezone(timezone.utc).isoformat(timespec="seconds")
    except ValueError:
        return value
