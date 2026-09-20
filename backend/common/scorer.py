"""Pass 3: score fit, using a Strands agent.

Unlike extraction -- a pure transform with no decisions -- scoring genuinely
benefits from an agent loop. The model can pull the candidate's profile, look
up what else the employer has open, and reason about the combination before
committing to a number. That is a real reason-act cycle, not a single call
dressed up as one.

Only gate survivors reach this function, so the expensive model runs on a small
fraction of the corpus.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from pydantic import BaseModel, Field
from strands import Agent, tool
from strands.models import BedrockModel

from .profile import Profile

log = logging.getLogger(__name__)

# Strands talks to bedrock-runtime, the same surface extractor.py now uses, so
# this is an inference-profile id. Nova Pro rather than a Marketplace-brokered
# model: third-party models on Bedrock require a credit-card Marketplace
# subscription that fails with INVALID_PAYMENT_INSTRUMENT on many accounts.
SCORE_MODEL_ID = os.environ.get("SCORE_MODEL", "us.amazon.nova-pro-v1:0")
AWS_REGION = os.environ.get("BEDROCK_REGION", os.environ.get("AWS_REGION", "us-east-1"))


class FitAssessment(BaseModel):
    """What the scorer must return. Enforced by Strands via structured output."""

    fit_score: int = Field(ge=0, le=100, description="0-100, using the full range. See the score bands.")
    why: str = Field(
        max_length=220,
        description=(
            "One sentence. Name something specific from THIS posting (team, product, "
            "stack, problem) and connect it to something concrete in the candidate "
            "profile. Must not be a sentence that would fit any other posting."
        ),
    )
    gaps: list[str] = Field(default_factory=list, description="Up to 3 concrete things the posting wants that the candidate lacks.")
    strengths: list[str] = Field(default_factory=list, description="Up to 3 things the candidate has that this role wants.")
    credibility_concern: str | None = Field(
        default=None,
        description=(
            "EMPLOYER LEGITIMACY ONLY. Set when this is probably not a real vacancy "
            "at a real employer -- training institute, certificate mill, staffing "
            "advert with no end client, duplicate spam, job-board-slug company name. "
            "Never for wrong city, contract length, missing skills or a thin "
            "description. Null in almost every case."
        ),
    )


SYSTEM_PROMPT = """\
You assess how well a job posting fits one specific candidate. The posting has \
already cleared a hard eligibility gate, so do not re-litigate eligibility -- \
assume the candidate may apply. Judge fit and quality.

Always call get_candidate_profile first. Everything you say about the candidate \
must come from that profile, never from assumption.

WRITING THE `why`
Name something specific from THIS posting -- the team, the product, the stack, \
the problem. Then connect it to something concrete in the profile.

  Bad:  "The candidate's skills in Python and AWS align with the role."
  Good: "Builds retrieval pipelines on Bedrock; candidate has shipped RAG with
         PyTorch and deployed on AWS."

If two postings could swap `why` lines without anyone noticing, both are too \
vague. A sentence that would fit any posting is worthless to the reader.

SCORING
Use the full range. A list where everything is 60-70 tells the reader nothing.

  85-100  the work itself matches what the candidate has actually done, and the
          posting names a stack they know
  70-84   clearly the right kind of role; some named requirements are missing
  50-69   right family, but the specifics diverge or the posting is too vague
          to tell
  30-49   technically eligible, weak overlap
  0-29    barely related, or the posting carries almost no information

Anchor on the WORK, not on keyword overlap. "Python" appearing in both is not a \
match -- everything lists Python.

`credibility_concern` IS ONLY FOR EMPLOYER LEGITIMACY
Set it when the posting looks like it is not a genuine vacancy at a real \
employer. Signals: the employer describes itself as providing training, courses \
or certificates to students rather than as a company with a product; an \
"internship" that charges, promises a certificate as the main benefit, or is \
unpaid with no named team; a staffing agency advert with no end client; the \
same listing repeated under many ids; a company name that is a job-board slug \
("IT Jobs Hyderabad", "vacancy global") rather than a business.

Do NOT use it for ordinary mismatches. These are NOT credibility concerns:
  - the role is in another city or country
  - the contract length, duration or notice period
  - the posting wanting skills the candidate lacks
  - a thin description from a source that truncates text

Those belong in `gaps` or simply lower the score. Leave credibility_concern \
null unless you would warn a friend not to waste an application on it.

When a description is truncated or thin, say so plainly in `why` and score \
conservatively rather than inventing detail."""


def build_agent(profile: Profile, company_lookup) -> Agent:
    """Construct the scoring agent with its tools bound to this run's context."""

    @tool
    def get_candidate_profile() -> dict[str, Any]:
        """Fetch the candidate's background, skills and preferences."""
        return {
            "headline": profile.headline,
            "skills": profile.skills,
            "about": profile.about,
            "target_role_families": profile.role_families,
            "max_years_experience": profile.max_yoe,
            "preferred_cities": profile.preferred_cities,
        }

    @tool
    def get_employer_context(company: str) -> dict[str, Any]:
        """Look up what else this employer currently has open.

        An employer with many varied openings is usually a real company. One
        whose only listings are near-identical 'internships' is usually not.
        """
        return company_lookup(company)

    return Agent(
        model=BedrockModel(
            region_name=AWS_REGION,
            model_id=SCORE_MODEL_ID,
            max_tokens=2000,
        ),
        tools=[get_candidate_profile, get_employer_context],
        system_prompt=SYSTEM_PROMPT,
    )


def score_posting(agent: Agent, posting: dict[str, Any], extraction: dict[str, Any]) -> FitAssessment | None:
    """Score one posting. Returns None if the agent fails, so the caller can retry or skip."""
    confidence = posting.get("extraction_confidence", "full")
    prompt = f"""\
<posting>
<company>{posting.get('company')}</company>
<title>{posting.get('title')}</title>
<locations>{', '.join(posting.get('locations') or [])}</locations>
<source>{posting.get('source')}</source>
<description_completeness>{confidence}</description_completeness>
<extracted_facts>{extraction}</extracted_facts>
<description>
{(posting.get('description') or '')[:6000]}
</description>
</posting>

Assess the fit for this candidate."""

    try:
        result = agent(prompt, structured_output_model=FitAssessment)
    except Exception as exc:  # noqa: BLE001
        log.warning("scoring failed for %s: %s: %s", posting.get("posting_id"), type(exc).__name__, exc)
        return None

    # Strands returns the parsed model on the result; fall back defensively.
    parsed = getattr(result, "structured_output", None)
    if isinstance(parsed, FitAssessment):
        return parsed
    if isinstance(parsed, dict):
        try:
            return FitAssessment(**parsed)
        except Exception:  # noqa: BLE001
            return None
    return None
