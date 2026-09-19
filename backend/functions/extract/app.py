"""Stage 2: Bedrock reads each new posting.

Idempotent by design -- a posting that already carries `extracted_at` is
skipped, so re-running after a crash or a prompt tweak only pays for the rows
that still need work. That single check is the main cost control in the system.

The handler stops short of the Lambda timeout and reports `has_more`, letting
the state machine loop rather than forcing a longer function.
"""
from __future__ import annotations

import json
import logging
import time

from common.ddb import from_ddb, postings_table, query_stage, raw_table, to_ddb
from common.extractor import extract
from common.posting import utcnow

log = logging.getLogger()
log.setLevel(logging.INFO)

SAFETY_MARGIN_MS = 45_000   # leave room to finish the row in flight and return


def handler(event, context):
    table = postings_table()
    raw = raw_table()
    processed = skipped = failed = 0
    usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0}
    has_more = False

    for item in query_stage("new", limit=200):
        if context and context.get_remaining_time_in_millis() < SAFETY_MARGIN_MS:
            has_more = True
            break

        posting_id = item["posting_id"]
        if item.get("extracted_at"):
            skipped += 1
            continue

        raw_item = raw.get_item(Key={"posting_id": posting_id}).get("Item")
        if not raw_item:
            log.warning("no raw payload for %s", posting_id)
            failed += 1
            continue

        outcome = extract(from_ddb(raw_item))
        for key in usage:
            usage[key] += (outcome.usage or {}).get(key, 0)

        if outcome.ok:
            table.update_item(
                Key={"posting_id": posting_id},
                UpdateExpression=(
                    "SET extraction = :e, extracted_at = :t, pipeline_stage = :s "
                    "REMOVE quarantine_reason"
                ),
                ExpressionAttributeValues=to_ddb(
                    {":e": outcome.data, ":t": utcnow(), ":s": "extracted"}
                ),
            )
            processed += 1
        else:
            # Quarantine rather than write a half-trusted record. A posting we
            # could not read is strictly better absent than wrongly admitted.
            table.update_item(
                Key={"posting_id": posting_id},
                UpdateExpression=(
                    "SET pipeline_stage = :s, quarantine_reason = :r, extracted_at = :t"
                ),
                ExpressionAttributeValues=to_ddb(
                    {":s": "quarantined", ":r": outcome.error, ":t": utcnow()}
                ),
            )
            failed += 1

    result = {
        "processed": processed,
        "skipped": skipped,
        "quarantined": failed,
        "has_more": has_more,
        "usage": usage,
    }
    log.info("extract complete: %s", json.dumps(result))
    return result
