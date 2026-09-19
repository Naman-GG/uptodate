"""Pass 1 of the pipeline: read a job description, return eligibility facts.

This is deliberately *not* an agent. It is one call, one posting, one JSON
object out -- a pure transform with no tools and no loop. Determinism is the
whole point: a wrong `min_yoe` silently admits an ineligible posting.

Three defences against drift, in order of strength:
  1. A forced tool call constrains generation to the schema server-side.
  2. `validate_extraction` re-checks every field ourselves -- the model's
     schema adherence is necessary but not sufficient, since an enum can be
     satisfied by the wrong member.
  3. Anything still failing is quarantined, never written to the postings table.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from .converse import EXTRACT_MODEL, structured
from .schema import EXTRACTION_SCHEMA, ValidationError, validate_extraction
from .text import truncate_for_model

log = logging.getLogger(__name__)

# Kept byte-stable across the run: identical system text is what lets a model
# with prompt caching reuse the prefix instead of re-reading it per posting.
SYSTEM_PROMPT = """\
You read job postings and extract eligibility facts. You never decide whether a \
candidate should apply -- separate code makes that decision from the fields you return.

Rules:

1. Report what the posting SAYS, not what is typical for the role. If a field is \
not stated, infer conservatively and set the corresponding *_stated flag to false.

2. Seniority wording implies experience even when no number appears. "Senior", \
"Staff", "Principal", "Lead", "II"/"III" and "Manager" are experienced roles; \
treat them as at least 3 years unless the text says otherwise.

3. `is_technical` is about the WORK, not the employer and not the word "intern". \
A Talent Acquisition Intern at a software company is NOT technical. A Marketing \
Intern at an AI lab is NOT technical. Engineering, ML, data, security and \
infrastructure work IS technical.

4. `work_location_mode` is `remote_global` ONLY when the posting genuinely hires \
from any country. Company boilerplate such as "we are a remote-first company" or \
"we support fully remote work" does NOT qualify when the posting also names a \
required country, office or region. This distinction matters more than any other \
field -- err toward `remote_country` when in doubt.

5. `hires_from_india` is true when a candidate physically located in India could \
hold the role: an Indian office, Remote-India, or genuine global remote.

6. An internship is temporary by definition. A permanent role open to fresh \
graduates is `new_grad_fte`, not `internship`."""

_USER_TEMPLATE = """\
<posting>
<company>{company}</company>
<title>{title}</title>
<location_field>{location}</location_field>
<description>
{description}
</description>
</posting>

Extract the eligibility facts for this posting."""


@dataclass
class ExtractionOutcome:
    ok: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    attempts: int = 0
    usage: dict[str, int] | None = None


def build_user_message(posting: dict[str, Any]) -> str:
    locations = posting.get("locations") or []
    if isinstance(locations, str):
        locations = [locations]
    return _USER_TEMPLATE.format(
        company=posting.get("company", "unknown"),
        title=posting.get("title", ""),
        location=", ".join(locations) or "not stated",
        description=truncate_for_model(posting.get("description") or "", 12000),
    )


def extract(posting: dict[str, Any], *, max_attempts: int = 2) -> ExtractionOutcome:
    """Extract eligibility facts, retrying once if validation rejects the result."""
    last_error = "no attempt made"
    usage_total = {"input_tokens": 0, "output_tokens": 0}

    user_message = build_user_message(posting)
    correction = ""

    for attempt in range(1, max_attempts + 1):
        result = structured(
            system=SYSTEM_PROMPT,
            user=user_message + correction,
            schema=EXTRACTION_SCHEMA,
            model=EXTRACT_MODEL,
            max_tokens=1500,
        )

        for key in ("input_tokens", "output_tokens"):
            usage_total[key] += (result.usage or {}).get(key, 0)

        if not result.ok:
            last_error = result.error or "unknown converse failure"
            log.warning("extract attempt %s failed: %s", attempt, last_error)
            continue

        try:
            data = validate_extraction(result.data)
            return ExtractionOutcome(True, data, attempts=attempt, usage=usage_total)
        except ValidationError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            log.warning("extract attempt %s rejected: %s", attempt, last_error)
            # Tell the model precisely what we rejected. A bare retry usually
            # reproduces the same mistake.
            correction = (
                f"\n\nA previous attempt was rejected: {last_error}\n"
                "Correct that field and record the result again."
            )

    return ExtractionOutcome(False, None, last_error, max_attempts, usage_total)
