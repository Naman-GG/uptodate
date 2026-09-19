"""Pass 1 of the pipeline: read a job description, return eligibility facts.

This is deliberately *not* an agent. It is one call, one posting, one JSON
object out -- a pure transform with no tools and no loop. Determinism is the
whole point: a wrong `min_yoe` silently admits an ineligible posting.

Three defences against drift, in order of strength:
  1. `output_config.format` constrains generation to the schema server-side.
  2. `validate_extraction` re-checks every field ourselves.
  3. Anything still failing is quarantined, never written to the postings table.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from .bedrock import EXTRACT_MODEL, client
from .schema import EXTRACTION_SCHEMA, ValidationError, validate_extraction
from .text import truncate_for_model

log = logging.getLogger(__name__)

# Kept byte-stable: it is the cached prefix for every call in the run, so any
# per-posting text in here would cost us the cache hit on ~9,000 requests.
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
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": build_user_message(posting)}
    ]
    last_error = "no attempt made"
    usage_total = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0}

    for attempt in range(1, max_attempts + 1):
        try:
            response = client().messages.create(
                model=EXTRACT_MODEL,
                max_tokens=1500,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        # Stable across the whole run -- turns ~9k repeats of this
                        # prefix into cache reads instead of fresh input tokens.
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=messages,
                output_config={
                    "format": {"type": "json_schema", "schema": EXTRACTION_SCHEMA}
                },
            )
        except Exception as exc:  # noqa: BLE001 - surface any API failure as a quarantine
            last_error = f"bedrock call failed: {type(exc).__name__}: {exc}"
            log.warning("extract attempt %s failed: %s", attempt, last_error)
            continue

        for key in usage_total:
            usage_total[key] += getattr(response.usage, key, 0) or 0

        raw = next((b.text for b in response.content if b.type == "text"), "")
        try:
            data = validate_extraction(json.loads(raw))
            return ExtractionOutcome(True, data, attempts=attempt, usage=usage_total)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            log.warning("extract attempt %s rejected: %s", attempt, last_error)
            # Show the model its own bad output plus the specific complaint.
            messages = messages[:1] + [
                {"role": "assistant", "content": raw or "(empty)"},
                {
                    "role": "user",
                    "content": (
                        f"That response was rejected: {last_error}\n"
                        "Return a single JSON object matching the schema exactly."
                    ),
                },
            ]

    return ExtractionOutcome(False, None, last_error, max_attempts, usage_total)
