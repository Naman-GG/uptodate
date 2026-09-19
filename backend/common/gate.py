"""Deterministic eligibility gate.

The model reads; this code decides. Every rejection carries a machine-checkable
reason, which is what lets the UI explain *why* a posting never reached you --
and what makes the decision defensible when a judge pokes at it.

This module deliberately has no Bedrock dependency. The gate Lambda's IAM role
grants no bedrock:* permission at all, so "the LLM cannot decide eligibility"
is enforced by policy, not by convention.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .profile import INDIA_CITIES, Profile


@dataclass
class GateResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)   # why it failed
    matched: list[str] = field(default_factory=list)   # which rules it cleared

    def to_item(self) -> dict[str, Any]:
        return {"passed": self.passed, "reasons": self.reasons, "matched": self.matched}


def _location_ok(extraction: dict[str, Any], profile: Profile) -> tuple[bool, str]:
    mode = extraction.get("work_location_mode", "unclear")
    countries = {c.upper() for c in extraction.get("countries") or []}
    wanted = {c.upper() for c in profile.countries}
    cities = {c.lower() for c in extraction.get("cities") or []}

    if mode == "remote_global":
        if profile.include_remote_global:
            return True, "remote-global role, open from any country"
        return False, "global-remote roles excluded by profile"

    if countries & wanted:
        return True, f"located in {', '.join(sorted(countries & wanted))}"

    # Some boards name only a city, never a country. Recognise Indian cities
    # directly so we do not drop a genuine Bengaluru role over a missing code.
    if "IN" in wanted and (cities & set(INDIA_CITIES)):
        return True, "located in an Indian city"

    if extraction.get("hires_from_india") and "IN" in wanted:
        return True, "employer hires candidates based in India"

    found = ", ".join(sorted(countries)) or mode
    return False, f"location {found} not in {', '.join(sorted(wanted))}"


def evaluate(extraction: dict[str, Any], profile: Profile) -> GateResult:
    """Apply every hard rule. We collect *all* failures, not just the first --
    'needs 4 years and is US-only' is a more useful explanation than either alone.
    """
    reasons: list[str] = []
    matched: list[str] = []

    role_type = extraction.get("role_type", "unclear")
    if role_type in profile.role_types:
        matched.append(f"role type is {role_type.replace('_', ' ')}")
    else:
        reasons.append(f"role type {role_type.replace('_', ' ')} is not one of "
                       f"{', '.join(r.replace('_', ' ') for r in profile.role_types)}")

    min_yoe = extraction.get("min_yoe", 0)
    if min_yoe <= profile.max_yoe:
        matched.append(f"needs {min_yoe} yrs experience (limit {profile.max_yoe})")
    else:
        reasons.append(f"requires {min_yoe} years experience, profile allows {profile.max_yoe}")

    ok, detail = _location_ok(extraction, profile)
    (matched if ok else reasons).append(detail)

    auth = extraction.get("work_auth_constraint", "none")
    blocking = {"us_only", "eu_only", "uk_only", "other_restricted"}
    if auth in blocking and not ({"US", "EU", "UK"} & {c.upper() for c in profile.countries}):
        reasons.append(f"work authorisation restricted: {auth.replace('_', ' ')}")
    else:
        matched.append("no blocking work-authorisation requirement")

    family = extraction.get("role_family", "other")
    if family in profile.role_families:
        matched.append(f"{family.replace('_', ' ')} role")
    else:
        reasons.append(f"{family.replace('_', ' ')} is not a target role family")

    # Catches the "Talent Acquisition Intern at a tech company" class of false
    # positive that title keyword matching cannot distinguish.
    if profile.require_technical and not extraction.get("is_technical", False):
        reasons.append("non-technical role")
    elif profile.require_technical:
        matched.append("technical role")

    if profile.exclude_closed and extraction.get("posting_closed"):
        reasons.append("applications closed")

    if profile.enforce_grad_year and profile.grad_year:
        eligible = [str(y) for y in extraction.get("grad_years_eligible") or []]
        if not eligible:
            matched.append("no graduation year stated (not disqualifying)")
        elif str(profile.grad_year) in eligible:
            matched.append(f"open to {profile.grad_year} graduates")
        else:
            reasons.append(f"open to {', '.join(eligible)} graduates, not {profile.grad_year}")

    return GateResult(passed=not reasons, reasons=reasons, matched=matched)
