"""We validate the model's output ourselves rather than trusting it.

A wrong min_yoe silently admits an ineligible posting, which is the exact
failure this project exists to prevent.
"""
import pytest

from common.schema import ValidationError, validate_extraction

VALID = dict(
    role_type="internship", min_yoe=0, yoe_stated=True, grad_years_eligible=["2027"],
    work_location_mode="onsite", countries=["in"], cities=["Bengaluru"],
    hires_from_india=True, work_auth_constraint="none", role_family="ai_ml",
    is_technical=True, core_skills=["python"], degree_requirement="bachelors",
    posting_closed=False, one_line_summary="Build ML pipelines",
)


def test_accepts_a_well_formed_extraction():
    out = validate_extraction(VALID)
    assert out["role_type"] == "internship"
    assert out["countries"] == ["IN"], "country codes are normalised to upper case"


@pytest.mark.parametrize("patch,label", [
    ({"role_type": "fulltime"}, "enum not in the allowed set"),
    ({"min_yoe": "two"}, "non-integer experience"),
    ({"min_yoe": 99}, "experience out of range"),
    ({"is_technical": "yes"}, "string where boolean required"),
    ({"role_family": "wizardry"}, "unknown role family"),
    ({"work_location_mode": "hybrid-ish"}, "unknown location mode"),
])
def test_rejects_malformed_fields(patch, label):
    with pytest.raises(ValidationError):
        validate_extraction({**VALID, **patch})


@pytest.mark.parametrize("field", ["role_type", "min_yoe", "is_technical", "role_family"])
def test_rejects_missing_required_fields(field):
    payload = {k: v for k, v in VALID.items() if k != field}
    with pytest.raises(ValidationError):
        validate_extraction(payload)


def test_rejects_non_object():
    with pytest.raises(ValidationError):
        validate_extraction(["not", "an", "object"])


def test_list_fields_are_capped():
    out = validate_extraction({**VALID, "core_skills": [f"s{i}" for i in range(50)]})
    assert len(out["core_skills"]) <= 12
