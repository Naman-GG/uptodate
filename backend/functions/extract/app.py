"""Stage 2: Bedrock reads each screened posting.

Idempotent by design -- a posting that already carries `extracted_at` is
skipped, so re-running after a crash or a prompt change only pays for rows that
still need work. That single check is the main cost control in the system.

Extraction is the slow stage: one model call per posting, ~2.5s each. Run
sequentially, 3,700 postings would take over two hours and need a dozen Lambda
invocations. A thread pool turns that into minutes -- the work is entirely
network-bound, so threads are the right tool and the GIL is irrelevant.

Concurrency is deliberately modest. Bedrock throttles per-account, and botocore's
adaptive retry mode backs off on our behalf; pushing harder buys nothing but
429s and wasted spend on retried calls.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from common.ddb import from_ddb, postings_table, query_stage, raw_table, to_ddb
from common.extractor import extract
from common.posting import utcnow

log = logging.getLogger()
log.setLevel(logging.INFO)

SAFETY_MARGIN_MS = 60_000
MAX_WORKERS = int(os.environ.get("EXTRACT_CONCURRENCY", "6"))
BATCH = int(os.environ.get("EXTRACT_BATCH", "600"))

# Errors that say nothing about the posting, only about the moment we asked.
# These must never quarantine: the row stays at `new` and the next pass retries
# it. Recording a throttle as a content failure permanently discards a posting
# we simply asked for too quickly.
RETRYABLE = (
    "ThrottlingException",
    "TooManyRequestsException",
    "ServiceUnavailable",
    "ModelNotReadyException",
    "InternalServerException",
    "ReadTimeoutError",
    "ConnectTimeoutError",
    "EndpointConnectionError",
)


def _is_retryable(error: str) -> bool:
    return any(tag in (error or "") for tag in RETRYABLE)

_lock = threading.Lock()


def _process(item: dict, table, raw) -> str:
    """Extract one posting. Returns an outcome tag for the tally."""
    posting_id = item["posting_id"]
    if item.get("extracted_at"):
        return "skipped"

    raw_item = raw.get_item(Key={"posting_id": posting_id}).get("Item")
    if not raw_item:
        log.warning("no raw payload for %s", posting_id)
        return "failed"

    outcome = extract(from_ddb(raw_item))

    if not outcome.ok and _is_retryable(outcome.error or ""):
        # Leave the row untouched at `new`. No extracted_at stamp, so the next
        # pass picks it up again.
        return "throttled"

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
        with _lock:
            _usage["input_tokens"] += (outcome.usage or {}).get("input_tokens", 0)
            _usage["output_tokens"] += (outcome.usage or {}).get("output_tokens", 0)
        return "processed"

    # Quarantine rather than write a half-trusted record. A posting we could not
    # read is strictly better absent than wrongly admitted.
    table.update_item(
        Key={"posting_id": posting_id},
        UpdateExpression="SET pipeline_stage = :s, quarantine_reason = :r, extracted_at = :t",
        ExpressionAttributeValues=to_ddb(
            {":s": "quarantined", ":r": (outcome.error or "")[:400], ":t": utcnow()}
        ),
    )
    return "quarantined"


_usage = {"input_tokens": 0, "output_tokens": 0}


def handler(event, context):
    table = postings_table()
    raw = raw_table()
    _usage.update({"input_tokens": 0, "output_tokens": 0})

    backlog = list(query_stage("new", limit=BATCH))[:BATCH]
    tally = {"processed": 0, "skipped": 0, "quarantined": 0, "throttled": 0, "failed": 0}
    has_more = False

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_process, item, table, raw): item for item in backlog}
        for future in as_completed(futures):
            if context and context.get_remaining_time_in_millis() < SAFETY_MARGIN_MS:
                has_more = True
                # Let in-flight calls finish; cancel only what has not started.
                for f in futures:
                    f.cancel()
                break
            try:
                tally[future.result()] += 1
            except Exception as exc:  # noqa: BLE001 - one bad row must not kill the batch
                log.warning("worker error: %s: %s", type(exc).__name__, exc)
                tally["failed"] += 1

    if len(backlog) >= BATCH or tally["throttled"]:
        has_more = True

    result = {**tally, "has_more": has_more, "usage": dict(_usage),
              "concurrency": MAX_WORKERS}
    log.info("extract complete: %s", json.dumps(result))
    return result
