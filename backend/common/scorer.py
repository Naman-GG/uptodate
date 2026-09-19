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

    fit_score: int = Field(ge=0, le=100, description="0-100. Be strict: 80+ means genuinely strong.")
    why: str = Field(max_length=200, description="One sentence on why this matches, naming specifics from the posting.")
    gaps: list[str] = Field(default_factory=list, description="Up to 3 concrete things the posting wants that the candidate lacks.")
    strengths: list[str] = Field(default_factory=list, description="Up to 3 things the candidate has that this role wants.")
    credibility_concern: str | None = Field(
        default=None,
        description=(
            "Set when the posting looks like a training institute, an unpaid "
            "'certificate' internship, a staffing agency advert or a duplicate "
            "spam listing rather than a genuine employer vacancy. Null otherwise."
        ),
    )


SYSTEM_PROMPT = """\
You assess how well a job posting fits a candidate. The posting has already \
passed a hard eligibility gate, so do not re-litigate eligibility -- assume the \
candidate may apply. Your job is judgement about *fit and quality*.

Use the tools available to you. Fetch the candidate profile before scoring, and \
look up the employer when the posting's legitimacy is unclear.

Scoring discipline:
- 80-100: strong match on both the work and the candidate's actual skills
- 60-79: plausible, with real gaps
- 40-59: weak but not absurd
- below 40: technically eligible, poor fit

Be strict. A list where everything scores 85 is useless to the person reading it.

Watch for low-quality listings. The Indian internship market contains training \
institutes selling "internships" with certificates, staffing agencies posting \
generic adverts, and the same listing reposted many times. Signals: the employer \
describes itself as providing learning or career opportunities to students rather \
than as a company with a product; the posting promises a certificate; the role \
has no specific team or product. Flag these in credibility_concern -- the \
candidate deserves to know before spending an application on it.

When a description is short or truncated, say so in your reasoning and score \
conservatively rather than inventing detail that is not there."""


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
