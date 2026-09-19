"""The normalized posting record every adapter must produce.

One shape in DynamoDB regardless of source ATS. Adapters own all
source-specific quirks; nothing downstream should branch on `source`.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class RawPosting:
    posting_id: str          # "{source}#{company_token}#{native_id}" - dedups natively
    source: str              # greenhouse | lever | ashby | jsearch | paste
    company_token: str
    company: str
    title: str
    locations: list[str]
    description: str         # plain text, already flattened
    apply_url: str
    posted_at: str | None = None
    department: str | None = None
    employment_type: str | None = None
    compensation: str | None = None
    remote_hint: str | None = None   # source's own remote flag, if any

    # "full"    -> complete job description, extraction can trust the prose
    # "partial" -> description is truncated at the source (Adzuna caps at 500
    #              chars), so experience floors and grad years may be missing
    #              entirely rather than absent. Surfaced on the card so a
    #              low-confidence match is never presented as a certain one.
    extraction_confidence: str = "full"
    category_hint: str | None = None   # source-provided taxonomy, e.g. "IT Jobs"
    fetched_at: str = field(default_factory=utcnow)

    def to_item(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v not in (None, [], "")}

    @property
    def content_hash(self) -> str:
        """Detects when a posting's text actually changed, so re-ingest is cheap."""
        payload = f"{self.title}|{'|'.join(self.locations)}|{self.description}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


_WS = re.compile(r"\s+")


def clean_location(value: Any) -> list[str]:
    """Normalize the wildly different location shapes into a flat string list."""
    out: list[str] = []

    def push(v: Any) -> None:
        if not v:
            return
        if isinstance(v, str):
            # Sources variously use ';' , ' / ' or ',' between multiple offices.
            for part in re.split(r"\s*[;|]\s*|\s+/\s+", v):
                part = _WS.sub(" ", part).strip(" ,-")
                if part and part.lower() not in {"na", "n/a", "none"}:
                    out.append(part)
        elif isinstance(v, dict):
            push(v.get("name") or v.get("location") or v.get("addressLocality"))
        elif isinstance(v, (list, tuple)):
            for item in v:
                push(item)

    push(value)
    seen, deduped = set(), []
    for loc in out:
        key = loc.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(loc)
    return deduped
