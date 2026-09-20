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
            "One sentence that STARTS with what this posting asks for -- its product, "
            "team, system or named technology -- then says whether the candidate has "
            "done that. Must not begin with 'The candidate'. Must not reuse phrasing "
            "from another posting. If the posting names no team, product or stack, "
            "say so plainly."
        ),
    )
    gaps: list[str] = Field(default_factory=list, description="Up to 3 concrete things the posting wants that the candidate lacks.")
    strengths: list[str] = Field(default_factory=list, description="Up to 3 things the candidate has that this role wants.")
    # There is no credibility field. Judging whether an employer is genuine was
    # attempted with the model and with deterministic rules, and both produced
    # confident nonsense -- see the note in functions/score/app.py. The scorer
    # judges fit; a thin posting simply scores low and `why` says why.


SYSTEM_PROMPT = """\
You assess how well a job posting fits one specific candidate. The posting has \
already cleared a hard eligibility gate -- do not re-litigate eligibility. Judge \
fit and quality.

Call get_candidate_profile first. Call get_employer_context whenever the posting \
is thin, generic, or the employer name does not read like a real company.

WRITING THE `why` -- READ THIS TWICE
Start with what THIS POSTING asks for. Name a detail that appears in this \
description and nowhere else: the product, the team, the specific system, the \
named technology, the actual problem. Then say whether the candidate has done \
that.

Never begin with "The candidate". Begin with the role.

  Bad:  "The candidate's AI and ML experience, including building a Graph-RAG
         retrieval layer, aligns with the role's focus on AI systems."
  Good: "Wants someone to build evaluation harnesses for LLM features on a
         consumer banking app; candidate has shipped retrieval but no eval work."
  Good: "Recommendation ranking over GPU clusters -- far heavier infra than the
         candidate's ChromaDB and Neo4j work."

The second half must be as specific as the first. "Candidate has relevant AI and \
ML experience" is not an assessment -- it is filler. Name the actual thing they \
have done, or name what is missing:

  Filler: "...; candidate has relevant AI and ML experience."
  Real:   "...; candidate built Graph-RAG over Neo4j but has not worked at that scale."
  Real:   "...; nothing in the profile touches embedded systems."

Two postings must never be able to swap `why` lines.

When the posting genuinely says almost nothing -- no team, no product, no stack \
-- say exactly that: "Posting names no team, product or stack." That is useful \
information, not a failure.

SCORING -- USE THE WHOLE RANGE
  85-100  the posting names work the candidate has demonstrably done
  70-84   right kind of role, some named requirements missing
  50-69   right family, specifics diverge, or the posting is too vague to judge
  30-49   eligible but weak overlap
  0-29    barely related, or the posting carries almost no information

A vague posting cannot score above 65 however appealing the title. If you cannot \
name what the job involves, you cannot claim it is a strong match. Most postings \
should NOT land in the 70s.

DO NOT JUDGE THE EMPLOYER
You are not asked whether the company is real. Separate code decides that from
the shape of their postings, which is a fact rather than an impression. Judge
fit only. If a posting is thin, that lowers the score and belongs in `why`.

Write plain text. No HTML entities, no escaped quotes."""


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
