"""Candidate profile: the configurable half of the eligibility decision.

Stored as a DynamoDB record rather than baked into the Lambda, so a user edits
their criteria in the UI and the next pipeline run honours it -- no redeploy.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

INDIA_CITIES = (
    "bengaluru", "bangalore", "hyderabad", "mumbai", "pune", "delhi", "new delhi",
    "gurgaon", "gurugram", "noida", "chennai", "kolkata", "ahmedabad", "jaipur",
    "indore", "coimbatore", "kochi", "thiruvananthapuram", "chandigarh", "bhubaneswar",
)


@dataclass
class Profile:
    profile_id: str = "default"
    label: str = "Fresher / new grad"

    # --- hard eligibility criteria (consumed by the gate) ---
    role_types: list[str] = field(
        default_factory=lambda: ["internship", "new_grad_fte"]
    )
    max_yoe: int = 1
    role_families: list[str] = field(
        default_factory=lambda: ["software_engineering", "ai_ml", "data", "devops_infra", "security"]
    )
    require_technical: bool = True

    countries: list[str] = field(default_factory=lambda: ["IN"])
    include_remote_global: bool = True
    exclude_closed: bool = True

    # Optional and off by default: most postings never state a batch year, so
    # enforcing it would silently discard the majority of genuine matches.
    grad_year: str | None = None
    enforce_grad_year: bool = False

    # --- soft signals (consumed by the scorer, never by the gate) ---
    headline: str = "Final-year engineering student seeking AI/ML and software roles"
    skills: list[str] = field(
        default_factory=lambda: ["python", "pytorch", "sql", "aws", "react"]
    )
    about: str = ""
    preferred_cities: list[str] = field(default_factory=list)

    def to_item(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_item(cls, item: dict[str, Any] | None) -> "Profile":
        if not item:
            return cls()
        known = {f for f in cls().to_item()}
        clean = {k: v for k, v in item.items() if k in known}
        if "max_yoe" in clean:
            try:
                clean["max_yoe"] = int(clean["max_yoe"])
            except (TypeError, ValueError):
                clean.pop("max_yoe")
        return cls(**clean)


DEFAULT_PROFILE = Profile()
