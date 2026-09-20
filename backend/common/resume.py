"""Read a resume and propose profile fields from it.

Typing out your skills, background and target cities is the least interesting
part of using this, and a resume already contains all of it. Nova reads PDFs
natively through Converse document blocks, so the file goes to the model as-is
-- no PDF parsing library, no text extraction step of our own.

What comes back is a *proposal*, never a saved profile. The user sees the
fields populated and edits before saving: a resume says what someone has done,
not what they want next, and only they know the difference.
"""
from __future__ import annotations

import base64
import binascii
import logging
from typing import Any

from .converse import SCORE_MODEL, client, tool_input
from .profile import Profile

log = logging.getLogger(__name__)

MAX_BYTES = 5 * 1024 * 1024
SUPPORTED = {"pdf", "txt", "md", "html", "doc", "docx"}

SUGGEST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "headline": {
            "type": "string",
            "description": (
                "One line, first person, describing what this person is looking for "
                "next -- not a summary of their past. Max 100 characters."
            ),
        },
        "skills": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Up to 12 concrete technologies, languages, frameworks or methods, "
                "lowercase. Only things actually named in the resume. Skip soft "
                "skills and generic words like 'programming'."
            ),
        },
        "about": {
            "type": "string",
            "description": (
                "Two or three sentences a recruiter would find useful: what they "
                "have actually built, where they have worked, and what they studied. "
                "Concrete projects and technologies, not adjectives. Max 400 chars."
            ),
        },
        "preferred_cities": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Cities named as current location or preference. Empty if none stated.",
        },
        "grad_year": {
            "type": "string",
            "description": "Graduation year as four digits if stated, otherwise an empty string.",
        },
        "role_families": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["software_engineering", "ai_ml", "data", "devops_infra",
                         "security", "product", "design"],
            },
            "description": "Which fields this person's experience actually points at. One to three.",
        },
    },
    "required": ["headline", "skills", "about", "preferred_cities", "grad_year", "role_families"],
}

SYSTEM = """\
You read a resume and propose what to put in a job-search profile.

Report only what the document supports. If the resume never states a graduation \
year, return an empty string rather than guessing from dates. If no city is \
named, return an empty list.

For `skills`, list technologies the person has demonstrably used -- named in a \
project, a job, or a skills section. Do not pad the list.

For `about`, write what they have built and with what. A recruiter should be \
able to tell this person apart from any other candidate after reading it. \
Avoid "passionate", "motivated", "strong background"."""


class ResumeError(ValueError):
    pass


def suggest_profile(*, content_b64: str | None = None, filename: str = "resume.pdf",
                    text: str | None = None) -> dict[str, Any]:
    """Return proposed profile fields. Raises ResumeError on unusable input."""
    if text:
        content_block = {"text": f"<resume>\n{text[:40000]}\n</resume>"}
    else:
        if not content_b64:
            raise ResumeError("provide either a file or resume text")
        try:
            raw = base64.b64decode(content_b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ResumeError(f"file is not valid base64: {exc}") from None
        if len(raw) > MAX_BYTES:
            raise ResumeError(f"file is {len(raw) // 1024}KB; limit is {MAX_BYTES // 1024}KB")

        fmt = (filename.rsplit(".", 1)[-1] or "pdf").lower()
        if fmt not in SUPPORTED:
            raise ResumeError(f"unsupported file type '{fmt}'; use {', '.join(sorted(SUPPORTED))}")
        # Bedrock rejects document names with punctuation beyond spaces/hyphens.
        safe_name = "".join(c if c.isalnum() or c in " -" else " " for c in filename)[:60].strip() or "resume"
        content_block = {"document": {"name": safe_name, "format": fmt, "source": {"bytes": raw}}}

    response = client().converse(
        modelId=SCORE_MODEL,   # the stronger model; this runs once per upload
        system=[{"text": SYSTEM}],
        messages=[{"role": "user", "content": [
            content_block,
            {"text": "Propose profile fields from this resume."},
        ]}],
        inferenceConfig={"maxTokens": 1200, "temperature": 0},
        toolConfig={
            "tools": [{"toolSpec": {
                "name": "propose_profile",
                "description": "Record the proposed profile fields.",
                "inputSchema": {"json": SUGGEST_SCHEMA},
            }}],
            "toolChoice": {"tool": {"name": "propose_profile"}},
        },
    )

    proposed = tool_input(response)
    if not proposed:
        raise ResumeError("could not read any profile fields from that file")

    valid_families = set(SUGGEST_SCHEMA["properties"]["role_families"]["items"]["enum"])
    return {
        "headline": str(proposed.get("headline", ""))[:120],
        "skills": [str(s).strip().lower() for s in (proposed.get("skills") or [])][:12],
        "about": str(proposed.get("about", ""))[:500],
        # Cities are proper nouns; the model sometimes lowercases them.
        "preferred_cities": [str(c).strip().title() for c in (proposed.get("preferred_cities") or [])][:8],
        "grad_year": (str(proposed.get("grad_year", "")).strip() or None),
        "role_families": [f for f in (proposed.get("role_families") or []) if f in valid_families]
                          or list(Profile().role_families),
    }
