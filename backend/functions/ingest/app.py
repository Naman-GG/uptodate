"""Stage 1: pull every configured source into raw_postings.

Writes two rows per posting: the untouched payload in raw_postings (replayable
if a prompt change invalidates an extraction) and a lightweight row in postings
marked `pipeline_stage="new"` for the extractor to pick up.

Postings already present are left alone -- re-ingesting must not reset a card
a user has already moved on their board.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
from concurrent.futures import ThreadPoolExecutor, as_completed

from adapters import BOARD_REGISTRY, adzuna
from common.dedup import deduplicate
from common.prefilter import screen
from common.ddb import batch_put, postings_table, raw_table, to_ddb
from common.posting import RawPosting, utcnow

log = logging.getLogger()
log.setLevel(logging.INFO)

BOARDS_FILE = pathlib.Path(__file__).parent / "boards.json"
RAW_TTL_DAYS = 60

# Query-driven India coverage. Deliberately broad: precision is the gate's job,
# and a term that is too narrow here cannot be recovered downstream.
ADZUNA_QUERIES = [
    "software engineer intern",
    "machine learning intern",
    "data science intern",
    "graduate engineer trainee",
    "software developer fresher",
    "backend developer intern",
    "ai engineer intern",
]


def _fetch_board(source: str, token: str) -> list[RawPosting]:
    try:
        return BOARD_REGISTRY[source](token)
    except Exception as exc:  # noqa: BLE001 - one dead board must not fail the run
        log.warning("board %s/%s failed: %s: %s", source, token, type(exc).__name__, exc)
        return []


def _fetch_adzuna(query: str) -> list[RawPosting]:
    try:
        return adzuna.fetch(query, country="in", pages=2, max_days_old=45)
    except Exception as exc:  # noqa: BLE001
        log.warning("adzuna %r failed: %s: %s", query, type(exc).__name__, exc)
        return []


def handler(event, context):
    boards = json.loads(BOARDS_FILE.read_text())["boards"]
    only = (event or {}).get("sources")
    if only:
        boards = [b for b in boards if b["source"] in only]

    collected: list[RawPosting] = []
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = [pool.submit(_fetch_board, b["source"], b["token"]) for b in boards]
        if not only or "adzuna" in only:
            futures += [pool.submit(_fetch_adzuna, q) for q in ADZUNA_QUERIES]
        for future in as_completed(futures):
            collected.extend(future.result())

    fetched = len(collected)
    postings, dropped = deduplicate(collected)
    log.info("fetched=%s deduped=%s dropped=%s", fetched, len(postings), dropped)

    # Which ids do we already know about? Re-ingest must not clobber board state.
    table = postings_table()
    existing: set[str] = set()
    for posting in postings:
        resp = table.get_item(
            Key={"posting_id": posting.posting_id},
            ProjectionExpression="posting_id",
        )
        if resp.get("Item"):
            existing.add(posting.posting_id)

    fresh = [p for p in postings if p.posting_id not in existing]

    expires_at = int(__import__("time").time()) + RAW_TTL_DAYS * 86400
    batch_put(raw_table(), [{**p.to_item(), "expires_at": expires_at} for p in fresh])
    # Screen before writing, not before reading. Postings that no fresher could
    # take are still recorded -- the funnel needs to show what was discarded --
    # but they are parked at `prescreened_out` so the extractor never pays to
    # read them. Over the live corpus this is the difference between ~3.5k and
    # ~14.5k model calls.
    rows, screened_out = [], 0
    for p in fresh:
        verdict = screen(p.title, p.company, p.description)
        if not verdict.keep:
            screened_out += 1
        rows.append(
            {
                "posting_id": p.posting_id,
                "source": p.source,
                "company": p.company,
                "title": p.title,
                "locations": p.locations,
                "apply_url": p.apply_url,
                "posted_at": p.posted_at,
                "extraction_confidence": p.extraction_confidence,
                "content_hash": p.content_hash,
                "pipeline_stage": "new" if verdict.keep else "prescreened_out",
                "prescreen_reason": verdict.reason,
                "ingested_at": utcnow(),
            }
        )
    batch_put(table, rows)

    result = {
        "fetched": fetched,
        "after_dedup": len(postings),
        "duplicates_dropped": dropped,
        "already_known": len(existing),
        "new": len(fresh),
        "prescreened_out": screened_out,
        "to_extract": len(fresh) - screened_out,
        "boards": len(boards),
    }
    log.info("ingest complete: %s", json.dumps(result))
    return result
