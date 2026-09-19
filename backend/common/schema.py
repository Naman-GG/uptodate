"""The contract between the LLM extractor and the deterministic gate.

Every field here is something the gate or the scorer actually consumes. The
model's only job is to *read* the posting and fill these in; it never decides
whether a candidate is eligible. That decision lives in `gate.py`, in code we
can point at and defend.
"""
from __future__ import annotations

from typing import Any

ROLE_TYPES = ("internship", "new_grad_fte", "experienced_fte", "contract", "unclear")

ROLE_FAMILIES = (
    "software_engineering", "ai_ml", "data", "product", "design", "security",
    "devops_infra", "sales", "marketing", "operations", "hr_recruiting",
    "finance", "legal", "support", "other",
)

LOCATION_MODES = ("onsite", "hybrid", "remote_country", "remote_global", "unclear")

WORK_AUTH = ("none", "india_only", "us_only", "eu_only", "uk_only", "other_restricted")

DEGREE_REQUIREMENTS = ("none", "bachelors", "masters", "phd", "unclear")

# JSON Schema handed to Bedrock's tool-use API so the model returns structured
# output instead of prose we would have to parse out of a code fence.
EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "role_type": {
            "type": "string", "enum": list(ROLE_TYPES),
            "description": (
                "internship = temporary//co-op/trainee. new_grad_fte = permanent role "
                "explicitly open to final-year students, fresh graduates, or 0-1 years "
                "of experience. experienced_fte = permanent role expecting prior "
                "professional experience. unclear only if genuinely indeterminate."
            ),
        },
        "min_yoe": {
            "type": "integer", "minimum": 0, "maximum": 30,
            "description": (
                "Minimum years of professional experience required. Internships and "
                "roles open to fresh graduates are 0. If the posting says '2+ years' "
                "use 2; for a '3-5 years' range use 3. If nothing is stated, infer "
                "from seniority wording and set yoe_stated=false."
            ),
        },
        "yoe_stated": {
            "type": "boolean",
            "description": "True only if an explicit experience requirement appears in the text.",
        },
        "grad_years_eligible": {
            "type": "array", "items": {"type": "string"},
            "description": (
                "Graduation years the posting explicitly admits, e.g. ['2026','2027']. "
                "Empty array if the posting does not mention graduation year or batch."
            ),
        },
        "work_location_mode": {
            "type": "string", "enum": list(LOCATION_MODES),
            "description": (
                "remote_country = remote but tied to one country. remote_global = "
                "explicitly hires from anywhere / any country / work from anywhere. "
                "Boilerplate phrases like 'we are a remote-first company' do NOT make "
                "a role remote_global if the posting names a required country or office."
            ),
        },
        "countries": {
            "type": "array", "items": {"type": "string"},
            "description": "ISO-3166 alpha-2 codes the role can be performed from, e.g. ['IN','US'].",
        },
        "cities": {"type": "array", "items": {"type": "string"}},
        "hires_from_india": {
            "type": "boolean",
            "description": (
                "True if a candidate physically located in India could hold this role: "
                "an Indian office, Remote-India, or genuinely global remote."
            ),
        },
        "work_auth_constraint": {
            "type": "string", "enum": list(WORK_AUTH),
            "description": "Any hard right-to-work restriction stated in the posting.",
        },
        "role_family": {"type": "string", "enum": list(ROLE_FAMILIES)},
        "is_technical": {
            "type": "boolean",
            "description": (
                "True for engineering, ML, data and security roles. False for "
                "recruiting, marketing, design, sales and operations roles even when "
                "the title contains the word 'intern' or the employer is a tech company."
            ),
        },
        "core_skills": {
            "type": "array", "items": {"type": "string"},
            "description": "Up to 10 concrete technologies or methods, lowercase.",
        },
        "degree_requirement": {"type": "string", "enum": list(DEGREE_REQUIREMENTS)},
        "posting_closed": {
            "type": "boolean",
            "description": "True if the text says applications are closed or the deadline has passed.",
        },
        "one_line_summary": {
            "type": "string",
            "description": "Max 18 words, plain description of what the role actually does.",
        },
    },
    "required": [
        "role_type", "min_yoe", "yoe_stated", "grad_years_eligible",
        "work_location_mode", "countries", "hires_from_india",
        "work_auth_constraint", "role_family", "is_technical",
        "degree_requirement", "posting_closed", "one_line_summary",
    ],
    "additionalProperties": False,
}


class ValidationError(ValueError):
    pass


def validate_extraction(data: Any) -> dict[str, Any]:
    """Enforce the schema ourselves rather than trusting the model's word.

    Anything that fails here gets quarantined instead of polluting the table --
    a wrong `min_yoe` silently admits an ineligible posting, which is exactly
    the failure mode this whole project exists to prevent.
    """
    if not isinstance(data, dict):
        raise ValidationError(f"expected object, got {type(data).__name__}")

    missing = [f for f in EXTRACTION_SCHEMA["required"] if f not in data]
    if missing:
        raise ValidationError(f"missing required fields: {missing}")

    out: dict[str, Any] = {}
    enums = {
        "role_type": ROLE_TYPES, "role_family": ROLE_FAMILIES,
        "work_location_mode": LOCATION_MODES, "work_auth_constraint": WORK_AUTH,
        "degree_requirement": DEGREE_REQUIREMENTS,
    }
    for field, allowed in enums.items():
        value = str(data.get(field, "")).strip().lower()
        if value not in allowed:
            raise ValidationError(f"{field}={data.get(field)!r} not in {allowed}")
        out[field] = value

    try:
        yoe = int(data["min_yoe"])
    except (TypeError, ValueError):
        raise ValidationError(f"min_yoe not an integer: {data['min_yoe']!r}") from None
    if not 0 <= yoe <= 30:
        raise ValidationError(f"min_yoe out of range: {yoe}")
    out["min_yoe"] = yoe

    for field in ("yoe_stated", "hires_from_india", "is_technical", "posting_closed"):
        value = data.get(field)
        if not isinstance(value, bool):
            raise ValidationError(f"{field} must be boolean, got {value!r}")
        out[field] = value

    for field in ("grad_years_eligible", "countries", "cities", "core_skills"):
        value = data.get(field) or []
        if not isinstance(value, list):
            raise ValidationError(f"{field} must be a list, got {type(value).__name__}")
        out[field] = [str(v).strip() for v in value if str(v).strip()][:12]

    out["countries"] = [c.upper()[:2] for c in out["countries"] if len(str(c)) >= 2]
    out["one_line_summary"] = str(data.get("one_line_summary", "")).strip()[:160]
    return out
