"""Stage 3: decide eligibility. No model involved.

This function's IAM role grants DynamoDB access and nothing else -- it holds no
bedrock permission, so it cannot ask a model whether someone is eligible even
if a future edit tried to. That is the architectural claim of the project,
enforced by policy rather than by convention.

Every verdict carries its reasons, so the UI can explain precisely why a
posting never reached the board.
"""
from __future__ import annotations

import json
import logging

from common.ddb import from_ddb, postings_table, profiles_table, query_stage, to_ddb
from common.gate import evaluate
from common.posting import utcnow
from common.profile import DEFAULT_PROFILE, Profile

log = logging.getLogger()
log.setLevel(logging.INFO)


def _load_profile(profile_id: str) -> Profile:
    item = profiles_table().get_item(Key={"profile_id": profile_id}).get("Item")
    if not item:
        log.info("profile %r not found, using defaults", profile_id)
        return DEFAULT_PROFILE
    return Profile.from_item(from_ddb(item))


def handler(event, context):
    profile_id = (event or {}).get("profile_id", "default")
    profile = _load_profile(profile_id)
    table = postings_table()

    passed = blocked = 0
    reason_tally: dict[str, int] = {}

    for item in query_stage("extracted", limit=500):
        extraction = from_ddb(item.get("extraction") or {})
        if not extraction:
            continue

        verdict = evaluate(extraction, profile)
        for reason in verdict.reasons:
            key = reason.split(",")[0][:60]
            reason_tally[key] = reason_tally.get(key, 0) + 1

        table.update_item(
            Key={"posting_id": item["posting_id"]},
            UpdateExpression=(
                "SET gate_result = :g, pipeline_stage = :s, profile_id = :p, gated_at = :t"
            ),
            ExpressionAttributeValues=to_ddb(
                {
                    ":g": verdict.to_item(),
                    ":s": "gate_passed" if verdict.passed else "gate_blocked",
                    ":p": profile_id,
                    ":t": utcnow(),
                }
            ),
        )
        if verdict.passed:
            passed += 1
        else:
            blocked += 1

    result = {
        "profile_id": profile_id,
        "passed": passed,
        "blocked": blocked,
        "top_rejection_reasons": dict(
            sorted(reason_tally.items(), key=lambda kv: -kv[1])[:10]
        ),
    }
    log.info("gate complete: %s", json.dumps(result))
    return result
