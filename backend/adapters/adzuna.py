"""Adzuna aggregator API -- our India coverage.

GET https://api.adzuna.com/v1/api/jobs/{country}/search/{page}
Requires a free app_id/app_key pair.

Why this source exists: all 201 ATS boards together yield ~6 India-based
fresher technical roles. Adzuna returns thousands, because it aggregates the
Indian job market that Greenhouse/Lever/Ashby simply do not serve.

Two costs come with that reach, both handled here rather than downstream:

  * Descriptions are capped at 500 characters and truncated mid-sentence, so
    every record is marked `extraction_confidence="partial"`. The requirements
    block -- where the experience floor and graduation year live -- is usually
    the part that got cut.
  * Listings go stale and training institutes post internship-mill adverts.
    `max_days_old` prunes the first; the gate handles the second.
"""
from __future__ import annotations

import os
import urllib.parse
from datetime import datetime, timezone

from common.http import get_json
from common.posting import RawPosting, clean_location

BASE = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
MAX_RESULTS_PER_PAGE = 50          # Adzuna's hard ceiling
DEFAULT_MAX_DAYS_OLD = 30          # a fresher posting older than a month is noise


class MissingCredentials(RuntimeError):
    pass


def _credentials() -> tuple[str, str]:
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise MissingCredentials(
            "ADZUNA_APP_ID and ADZUNA_APP_KEY must be set to use the Adzuna adapter"
        )
    return app_id, app_key


def fetch(
    query: str,
    *,
    country: str = "in",
    pages: int = 1,
    max_days_old: int = DEFAULT_MAX_DAYS_OLD,
    category: str | None = None,
) -> list[RawPosting]:
    """Fetch postings for one search term.

    Unlike the ATS adapters -- which enumerate a company's whole board -- Adzuna
    is query-driven, so the caller supplies the search terms. Pagination is
    sequential because Adzuna has no documented per-key rate limit and we would
    rather stay polite than discover one mid-demo.
    """
    app_id, app_key = _credentials()
    out: list[RawPosting] = []

    for page in range(1, pages + 1):
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": MAX_RESULTS_PER_PAGE,
            "what": query,
            "max_days_old": max_days_old,
            "content-type": "application/json",
        }
        if category:
            params["category"] = category

        url = BASE.format(country=country, page=page) + "?" + urllib.parse.urlencode(params)
        payload = get_json(url, timeout=40)
        results = payload.get("results") or []
        if not results:
            break

        out.extend(p for p in (_parse(country, job) for job in results) if p)
        if len(results) < MAX_RESULTS_PER_PAGE:
            break  # last page

    return out


def _parse(country: str, job: dict) -> RawPosting | None:
    native_id = job.get("id")
    if not native_id:
        return None

    company = (job.get("company") or {}).get("display_name") or "Unknown"
    location_block = job.get("location") or {}
    # `area` is a hierarchy like ["India", "Maharashtra", "Pune"]; reversing it
    # puts the most specific place first, matching how the ATS sources read.
    area = [a for a in (location_block.get("area") or []) if a]
    locations = clean_location(location_block.get("display_name")) or clean_location(
        list(reversed(area))
    )

    category = (job.get("category") or {}).get("label")

    description = (job.get("description") or "").strip()
    # Adzuna truncates at 500 chars; the ellipsis is its own marker.
    truncated = len(description) >= 499 or description.endswith(("…", "..."))

    employment_type = job.get("contract_time") or job.get("contract_type")

    return RawPosting(
        posting_id=f"adzuna#{country}#{native_id}",
        source="adzuna",
        company_token=_slug(company),
        company=company,
        title=(job.get("title") or "").strip(),
        locations=locations,
        description=description,
        # redirect_url is an Adzuna tracking bounce, but it is the only apply
        # link the API exposes and it does reach the employer's posting.
        apply_url=job.get("redirect_url") or "",
        posted_at=_iso(job.get("created")),
        department=category,
        employment_type=employment_type.replace("_", " ") if employment_type else None,
        extraction_confidence="partial" if truncated else "full",
        category_hint=category,
    )


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")[:60]


def _iso(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return (
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            .astimezone(timezone.utc)
            .isoformat(timespec="seconds")
        )
    except ValueError:
        return value
