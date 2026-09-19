"""Ashby job board API.

GET https://api.ashbyhq.com/posting-api/job-board/{name}?includeCompensation=true
Keyless. Ships `descriptionPlain` already flattened plus a structured
`compensation` block that no other source gives us.
"""
from __future__ import annotations

from common.http import get_json
from common.posting import RawPosting, clean_location

ENDPOINT = (
    "https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true"
)


def fetch(token: str) -> list[RawPosting]:
    payload = get_json(ENDPOINT.format(token=token))
    jobs = payload.get("jobs") or []
    return [p for p in (_parse(token, job) for job in jobs) if p]


def _parse(token: str, job: dict) -> RawPosting | None:
    native_id = job.get("id")
    # Unlisted postings are drafts or already-closed roles.
    if not native_id or job.get("isListed") is False:
        return None

    locations = clean_location(job.get("location"))
    locations += [
        loc for loc in clean_location(job.get("secondaryLocations")) if loc not in locations
    ]

    comp = job.get("compensation") or {}
    comp_summary = (
        comp.get("compensationTierSummary")
        or comp.get("scrapeableCompensationSalarySummary")
        if isinstance(comp, dict)
        else None
    )

    remote = job.get("workplaceType")
    if not remote and job.get("isRemote") is True:
        remote = "Remote"

    return RawPosting(
        posting_id=f"ashby#{token}#{native_id}",
        source="ashby",
        company_token=token,
        company=token.replace("-", " ").title(),
        title=(job.get("title") or "").strip(),
        locations=locations,
        description=(job.get("descriptionPlain") or "").strip(),
        apply_url=job.get("jobUrl") or job.get("applyUrl") or "",
        posted_at=job.get("publishedAt"),
        department=job.get("department") or job.get("team"),
        employment_type=job.get("employmentType"),
        compensation=comp_summary,
        remote_hint=remote,
    )
