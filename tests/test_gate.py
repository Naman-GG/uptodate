"""The gate is where eligibility is decided, so it is where correctness matters.

Each case below is drawn from a posting that actually appeared in the live
corpus, not invented. The Paytm and MongoDB cases are the two that keyword
matching gets wrong, and they are the reason this project exists.
"""
import pytest

from common.gate import evaluate
from common.profile import Profile


def extraction(**overrides):
    base = dict(
        role_type="internship", min_yoe=0, yoe_stated=False, grad_years_eligible=[],
        work_location_mode="onsite", countries=["IN"], cities=["Bengaluru"],
        hires_from_india=True, work_auth_constraint="none",
        role_family="software_engineering", is_technical=True,
        degree_requirement="bachelors", posting_closed=False, one_line_summary="",
    )
    base.update(overrides)
    return base


def test_india_swe_intern_passes():
    """Stripe, Software Engineer Intern, Bengaluru."""
    assert evaluate(extraction(), Profile()).passed


def test_non_technical_intern_is_blocked():
    """Paytm, Intern-Talent Acquisition, Bangalore.

    Right seniority, right country, right role type, wrong work entirely. A
    keyword search for 'intern in India' surfaces this at the top.
    """
    result = evaluate(extraction(role_family="hr_recruiting", is_technical=False), Profile())
    assert not result.passed
    assert any("non-technical" in r for r in result.reasons)


def test_experienced_role_is_blocked_on_yoe():
    result = evaluate(extraction(role_type="experienced_fte", min_yoe=6, yoe_stated=True), Profile())
    assert not result.passed
    # Both failures are reported, not just the first -- a partial explanation
    # is worse than none when the user is deciding whether to trust the tool.
    assert len(result.reasons) >= 2


def test_us_only_new_grad_is_blocked():
    result = evaluate(
        extraction(role_type="new_grad_fte", countries=["US"], cities=["San Francisco"],
                   hires_from_india=False, work_auth_constraint="us_only"),
        Profile(),
    )
    assert not result.passed
    assert any("work authorisation" in r for r in result.reasons)


def test_global_remote_passes_when_profile_allows():
    ex = extraction(role_type="new_grad_fte", min_yoe=1, work_location_mode="remote_global",
                    countries=[], cities=[], role_family="ai_ml")
    assert evaluate(ex, Profile(include_remote_global=True)).passed


def test_global_remote_blocked_when_profile_excludes():
    ex = extraction(role_type="new_grad_fte", min_yoe=1, work_location_mode="remote_global",
                    countries=[], cities=[], role_family="ai_ml")
    result = evaluate(ex, Profile(include_remote_global=False))
    assert not result.passed


def test_indian_city_recognised_without_country_code():
    """Some boards give a city and no country. Dropping those loses real matches."""
    assert evaluate(extraction(countries=[], cities=["Bengaluru"]), Profile()).passed


def test_grad_year_not_enforced_by_default():
    """Most postings never state a batch year; enforcing it by default would
    discard the majority of genuine matches."""
    assert evaluate(extraction(grad_years_eligible=["2025"]), Profile()).passed


def test_grad_year_enforced_when_requested():
    profile = Profile(grad_year="2027", enforce_grad_year=True)
    result = evaluate(extraction(grad_years_eligible=["2025"]), profile)
    assert not result.passed


def test_unstated_grad_year_is_not_disqualifying():
    profile = Profile(grad_year="2027", enforce_grad_year=True)
    assert evaluate(extraction(grad_years_eligible=[]), profile).passed


def test_closed_posting_is_blocked():
    result = evaluate(extraction(posting_closed=True), Profile())
    assert not result.passed


def test_every_rejection_carries_a_reason():
    """A card the user never sees must still be explainable."""
    result = evaluate(extraction(role_family="sales", is_technical=False, min_yoe=9), Profile())
    assert not result.passed
    assert result.reasons and all(r.strip() for r in result.reasons)
