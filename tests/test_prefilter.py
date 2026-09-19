"""The prefilter must be cheap and conservative.

Cheap, because it exists to avoid paying a model to read postings no fresher
could take. Conservative, because anything it drops is never seen again -- and
it must never grow into the keyword filter this project exists to replace.
"""
import pytest

from common.prefilter import screen


@pytest.mark.parametrize("title", [
    "Software Engineer, Intern",
    "Graduate Engineer Trainee",
    "DS/ML Intern",
    "Ai Engg Intern",
    "Software Engineer (CPD) - Winter Intern",
    "Machine Learning Engineer Intern",
    "Software Engineer",
    "Backend Developer",
    "Associate Software Engineer I",
])
def test_keeps_plausible_fresher_roles(title):
    assert screen(title).keep, title


@pytest.mark.parametrize("title,reason", [
    ("Senior Staff Software Engineer - Backend", "senior title"),
    ("Principal Data Scientist", "senior title"),
    ("Engineering Manager, Terminal", "senior title"),
    ("Director of Platform", "senior title"),
    ("Software Engineer 3", "senior level marker"),
    ("Data Scientist III", "senior level marker"),
    ("Intern-Talent Acquisition", "non-technical title"),
    ("Video Editor Intern", "non-technical title"),
    ("Account Executive, Named - Germany", "non-technical title"),
    ("Assistant Manager - Internal Audit", "senior title"),
])
def test_drops_what_no_fresher_could_take(title, reason):
    result = screen(title)
    assert not result.keep, title
    assert result.reason == reason


def test_early_career_marker_beats_seniority_regex():
    """'Senior Year Intern' is an internship, not a senior role. Without the
    override the seniority check would silently discard it."""
    assert screen("Senior Year Software Intern").keep


def test_training_provider_needs_context_not_just_a_title():
    """Optimspace's title is indistinguishable from a real ML internship.
    Catching it requires reading, which is the model's job -- so the prefilter
    lets it through and the scoring agent flags it."""
    assert screen("Machine Learning Intern", company="Optimspace").keep


def test_explicit_training_language_is_dropped():
    assert not screen("Python Developer", company="Proxima Skills Academy",
                      description="A certification course with placement guarantee.").keep


def test_empty_title_is_dropped():
    assert not screen("").keep
