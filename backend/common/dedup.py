"""Cross-source deduplication.

Two ways the same job reaches us twice:
  * 14 companies run boards on more than one ATS (alloy, anyscale, axiom,
    finch, ghost, hightouch, knock, lovable, method, neon, orca, porter,
    secureframe, socket).
  * Adzuna aggregates postings that we also pull directly from the employer's
    board -- Coinbase is a live example.

When it happens we keep the ATS record, because it carries the full description
and a canonical apply link rather than a tracking bounce.
"""
from __future__ import annotations

import re
from collections import defaultdict

from .posting import RawPosting

# Higher wins. Full-text ATS records beat the truncated aggregator record.
SOURCE_RANK = {"greenhouse": 4, "lever": 4, "ashby": 4, "adzuna": 1, "paste": 0}

_NOISE = re.compile(
    r"\b(intern|internship|full[- ]time|part[- ]time|remote|hybrid|onsite|"
    r"\d{4}|summer|winter|fall|spring|new grad|graduate)\b",
    re.I,
)
_NONWORD = re.compile(r"[^a-z0-9]+")


def _norm(text: str) -> str:
    text = _NOISE.sub(" ", (text or "").lower())
    return _NONWORD.sub(" ", text).strip()


def _company_key(posting: RawPosting) -> str:
    name = _NONWORD.sub("", (posting.company or "").lower())
    # "MongoDB Inc" and "MongoDB" should collide.
    for suffix in ("inc", "llc", "ltd", "limited", "pvt", "private", "corp", "technologies"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name


def _city_key(posting: RawPosting) -> str:
    if not posting.locations:
        return ""
    first = posting.locations[0].lower()
    # Compare on city only; sources disagree on how much of the address to give.
    return _NONWORD.sub("", first.split(",")[0])


def fingerprint(posting: RawPosting) -> tuple[str, str, str]:
    return (_company_key(posting), _norm(posting.title), _city_key(posting))


def deduplicate(postings: list[RawPosting]) -> tuple[list[RawPosting], int]:
    """Collapse duplicates, preferring the richest source. Returns (kept, dropped)."""
    buckets: dict[tuple[str, str, str], list[RawPosting]] = defaultdict(list)
    for posting in postings:
        buckets[fingerprint(posting)].append(posting)

    kept: list[RawPosting] = []
    dropped = 0
    for group in buckets.values():
        if len(group) == 1:
            kept.append(group[0])
            continue
        group.sort(
            key=lambda p: (SOURCE_RANK.get(p.source, 0), len(p.description or "")),
            reverse=True,
        )
        kept.append(group[0])
        dropped += len(group) - 1
    return kept, dropped
