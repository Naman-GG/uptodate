"""Live extraction against real postings.

Skipped unless RUN_LIVE=1, because each run costs money and needs AWS
credentials. These are the cases that decide whether the pipeline is
trustworthy, so they are worth the cents when you do run them:

    RUN_LIVE=1 .venv/bin/python -m pytest tests/test_extraction_live.py -v
"""
import json
import os
import pathlib

import pytest

from common.extractor import extract
from common.gate import evaluate
from common.profile import Profile

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE") != "1", reason="set RUN_LIVE=1 to call Bedrock"
)

FIXTURES = json.loads((pathlib.Path(__file__).parent / "fixtures" / "postings.json").read_text())


def _extract(f):
    return extract(
        {
            "company": f["company"],
            "title": f["title"],
            "locations": [f["location"]],
            "description": f["description"],
        }
    )


@pytest.mark.parametrize("f", FIXTURES, ids=lambda f: f["fixture_id"])
def test_extraction_matches_expectations(f):
    out = _extract(f)
    assert out.ok, f"extraction failed: {out.error}"

    for field, expected in f.get("expect", {}).items():
        actual = out.data.get(field)
        assert str(actual).lower() == str(expected).lower(), (
            f"{field}: expected {expected!r}, got {actual!r}"
        )

    for field, forbidden in f.get("must_not", {}).items():
        assert str(out.data.get(field)).lower() != str(forbidden).lower(), (
            f"{field} must not be {forbidden!r}"
        )


def test_non_technical_intern_is_blocked_end_to_end():
    """Paytm's Talent Acquisition Intern -- the posting a keyword search for
    'intern in India' puts at the top."""
    f = next(x for x in FIXTURES if "Talent Acquisition" in x["title"])
    out = _extract(f)
    assert out.ok
    assert out.data["is_technical"] is False
    assert not evaluate(out.data, Profile()).passed


def test_remote_boilerplate_does_not_become_global_remote():
    """A senior US finance role whose description contains 'fully remote'
    boilerplate must not be read as hiring from anywhere."""
    f = next(x for x in FIXTURES if x["label"].startswith("trap:"))
    out = _extract(f)
    assert out.ok
    assert out.data["work_location_mode"] != "remote_global"
    assert not evaluate(out.data, Profile()).passed
