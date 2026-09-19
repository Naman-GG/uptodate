"""Cheap deterministic screening, applied before any model sees a posting.

Extraction is the only per-posting cost in the system, so anything we can rule
out with string matching is money not spent. Over the live corpus this removes
more than half the rows.

The rule for what belongs here: only signals that are unambiguous in the title
alone. Anything needing the description read -- experience floors, graduation
years, whether "remote" means remote-from-India -- stays with the model. This
file must never become the keyword filter the project exists to replace.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Seniority stated in the title. A Staff Engineer role is not a fresher role,
# and no amount of reading the description will change that.
SENIOR_TITLE = re.compile(
    r"\b(senior|sr\.?|staff|principal|distinguished|lead|leader|head\s+of|"
    r"director|vp|vice\s+president|chief|president|architect|"
    r"manager|mgr\.?|supervisor|partner|fellow)\b",
    re.I,
)

# Roman/numeric level markers that imply an experience ladder: "Engineer III",
# "Engineer 3". Deliberately excludes "I" and "1", which are entry-level.
SENIOR_LEVEL = re.compile(r"\b(?:engineer|developer|scientist|analyst|designer)\s*[-–]?\s*(?:I{2,3}|IV|V|[2-9])\b", re.I)

# Plainly not a technical individual-contributor track, by title alone.
NON_TECHNICAL_TITLE = re.compile(
    r"\b(recruit(er|ing|ment)|talent\s+acquisition|human\s+resources|\bhr\b|"
    r"payroll|accountant|accounting|bookkeep|auditor|\baudit\b|tax\b|"
    r"sales|account\s+executive|business\s+development|\bbdr\b|\bsdr\b|"
    r"marketing|seo\b|copywrit|content\s+writer|social\s+media|"
    r"customer\s+success|customer\s+support|call\s+centre|call\s+center|"
    r"legal|counsel|paralegal|compliance\s+officer|"
    r"video\s+editor|graphic\s+design|photograph|"
    r"facilit(y|ies)|housekeep|driver|warehouse|logistics\s+associate|"
    r"nurse|pharmacist|teacher|tutor)\b",
    re.I,
)

# Training institutes and certificate mills selling "internships" rather than
# hiring. Found in real Adzuna results (Optimspace, MAXGEN) at rank one.
TRAINING_MILL = re.compile(
    r"\b(training\s+institute|skills?\s+academy|certification\s+course|"
    r"placement\s+guarantee|paid\s+training\s+program|learn\s+and\s+earn)\b",
    re.I,
)


@dataclass
class PrefilterResult:
    keep: bool
    reason: str | None = None


def screen(title: str, company: str = "", description: str = "") -> PrefilterResult:
    """Decide whether a posting is worth spending an extraction call on."""
    title = (title or "").strip()
    if not title:
        return PrefilterResult(False, "no title")

    # An explicit internship or new-grad marker overrides the seniority check:
    # "Senior Year Intern" and "Graduate Engineer Trainee" must survive.
    early_marker = re.search(
        r"\b(intern|internship|trainee|apprentice|fresher|new\s*grad|graduate\s+(engineer|program|trainee)|"
        r"campus|entry[\s-]level|early\s+career)\b",
        title,
        re.I,
    )

    if not early_marker:
        if SENIOR_TITLE.search(title):
            return PrefilterResult(False, "senior title")
        if SENIOR_LEVEL.search(title):
            return PrefilterResult(False, "senior level marker")

    if NON_TECHNICAL_TITLE.search(title):
        return PrefilterResult(False, "non-technical title")

    if TRAINING_MILL.search(f"{company} {description[:600]}"):
        return PrefilterResult(False, "training provider, not an employer")

    return PrefilterResult(True)
