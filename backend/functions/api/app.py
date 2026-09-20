"""Read/write API behind API Gateway.

Routes:
  GET    /postings          board contents for a profile, ordered by fit
  PATCH  /postings/{id}     move a card between columns, or delete it
  GET    /funnel            the counts that make the triage visible
  GET    /profile           current criteria
  PUT    /profile           update criteria (the gate honours it next run)
  POST   /evaluate          run one pasted description through the pipeline
  POST   /profile/suggest   propose profile fields from an uploaded resume
"""
from __future__ import annotations

import json
import logging
import os

from boto3.dynamodb.conditions import Key

from common.ddb import from_ddb, postings_table, profiles_table, to_ddb
from common.extractor import extract
from common.gate import evaluate
from common.posting import utcnow
from common.profile import DEFAULT_PROFILE, Profile
from common.resume import ResumeError, suggest_profile

log = logging.getLogger()
log.setLevel(logging.INFO)

COLUMNS = {"new", "applied", "interviewing"}
CORS = {
    "content-type": "application/json",
    "access-control-allow-origin": "*",
    "access-control-allow-headers": "content-type",
    "access-control-allow-methods": "GET,POST,PATCH,DELETE,OPTIONS",
}


def _reply(status: int, body) -> dict:
    return {"statusCode": status, "headers": CORS, "body": json.dumps(body, default=str)}


def _profile(profile_id: str = "default") -> Profile:
    item = profiles_table().get_item(Key={"profile_id": profile_id}).get("Item")
    return Profile.from_item(from_ddb(item)) if item else DEFAULT_PROFILE


def handler(event, context):
    method = (event.get("requestContext", {}).get("http", {}).get("method") or "GET").upper()
    path = event.get("rawPath") or "/"
    params = event.get("queryStringParameters") or {}
    profile_id = params.get("profile_id", "default")

    try:
        body = json.loads(event["body"]) if event.get("body") else {}
    except json.JSONDecodeError:
        return _reply(400, {"error": "body is not valid JSON"})

    if method == "OPTIONS":
        return _reply(204, "")

    try:
        if path.endswith("/postings") and method == "GET":
            return _list_postings(profile_id, params)
        if "/postings/" in path and method in ("PATCH", "DELETE"):
            return _update_posting(path.rsplit("/", 1)[-1], method, body)
        if path.endswith("/funnel") and method == "GET":
            return _funnel(profile_id)
        if path.endswith("/profile") and method == "GET":
            return _reply(200, _profile(profile_id).to_item())
        if path.endswith("/profile") and method == "PUT":
            return _put_profile(profile_id, body)
        if path.endswith("/evaluate") and method == "POST":
            return _evaluate(profile_id, body)
        if path.endswith("/profile/suggest") and method == "POST":
            return _suggest_from_resume(body)
    except Exception as exc:  # noqa: BLE001
        log.exception("handler error")
        return _reply(500, {"error": f"{type(exc).__name__}: {exc}"})

    return _reply(404, {"error": f"no route for {method} {path}"})


def _list_postings(profile_id: str, params: dict) -> dict:
    limit = min(int(params.get("limit", 100)), 200)
    resp = postings_table().query(
        IndexName="by-profile-fit",
        KeyConditionExpression=Key("profile_id").eq(profile_id),
        ScanIndexForward=False,          # highest fit first
        Limit=limit,
    )
    items = [from_ddb(i) for i in resp.get("Items", [])]
    items = [i for i in items if i.get("pipeline_stage") == "scored"]

    column = params.get("column")
    if column:
        items = [i for i in items if i.get("board_column") == column]

    if params.get("hide_flagged") == "true":
        items = [i for i in items if not i.get("credibility_concern")]

    return _reply(200, {"count": len(items), "postings": items})


def _update_posting(posting_id: str, method: str, body: dict) -> dict:
    table = postings_table()
    if method == "DELETE" or body.get("column") == "rejected":
        # Rejected is a hard delete by design -- a rejected card should never
        # come back on the next pipeline run, and keeping it costs board space.
        table.delete_item(Key={"posting_id": posting_id})
        return _reply(200, {"posting_id": posting_id, "deleted": True})

    column = body.get("column")
    if column not in COLUMNS:
        return _reply(400, {"error": f"column must be one of {sorted(COLUMNS)}"})

    table.update_item(
        Key={"posting_id": posting_id},
        UpdateExpression="SET board_column = :c, moved_at = :t",
        ExpressionAttributeValues=to_ddb({":c": column, ":t": utcnow()}),
    )
    return _reply(200, {"posting_id": posting_id, "column": column})


def _funnel(profile_id: str) -> dict:
    """The counts that make the middle of the pipeline visible.

    A board showing twelve cards says nothing about the work done to get there.
    These numbers are the product.
    """
    table = postings_table()
    stages = [
        "new", "prescreened_out", "extracted", "quarantined",
        "gate_passed", "gate_blocked", "scored",
    ]
    counts = {}
    for stage in stages:
        # A DynamoDB query returns at most 1 MB per call, and Select=COUNT is no
        # exception -- it counts only what that page scanned. Without following
        # LastEvaluatedKey the funnel silently under-reports, which on a 14k
        # table showed 2,553 instead of 14,526.
        total = 0
        kwargs = {
            "IndexName": "by-stage",
            "KeyConditionExpression": Key("pipeline_stage").eq(stage),
            "Select": "COUNT",
        }
        while True:
            resp = table.query(**kwargs)
            total += resp.get("Count", 0)
            token = resp.get("LastEvaluatedKey")
            if not token:
                break
            kwargs["ExclusiveStartKey"] = token
        counts[stage] = total

    counts["total_ingested"] = sum(counts[s] for s in stages)

    # pipeline_stage is where a posting is NOW, not where it has been. A posting
    # that reached `scored` stopped being counted as `extracted` the moment the
    # gate moved it on -- so the raw stage counts report 0 read and 0 eligible
    # once the pipeline drains. The funnel needs cumulative progress, so derive
    # each step from every stage at or beyond it.
    counts["screened"] = counts["total_ingested"] - counts["prescreened_out"]
    counts["read"] = counts["gate_passed"] + counts["gate_blocked"] + counts["scored"]
    counts["eligible"] = counts["gate_passed"] + counts["scored"]
    counts["awaiting_extraction"] = counts["new"] + counts["extracted"]
    return _reply(200, counts)


def _put_profile(profile_id: str, body: dict) -> dict:
    merged = {**DEFAULT_PROFILE.to_item(), **body, "profile_id": profile_id}
    profile = Profile.from_item(merged)
    profiles_table().put_item(Item=to_ddb({**profile.to_item(), "updated_at": utcnow()}))
    return _reply(200, profile.to_item())


def _evaluate(profile_id: str, body: dict) -> dict:
    """Run one pasted description through extract -> gate, without persisting.

    Covers everything our sources do not: LinkedIn, Naukri, Unstop, a PDF a
    friend forwarded. Same pipeline, same verdict format.
    """
    description = (body.get("description") or "").strip()
    if len(description) < 80:
        return _reply(400, {"error": "description too short to assess"})

    posting = {
        "company": body.get("company", "Unknown"),
        "title": body.get("title", "Pasted role"),
        "locations": body.get("locations") or [],
        "description": description,
    }
    outcome = extract(posting)
    if not outcome.ok:
        return _reply(422, {"error": "could not extract eligibility facts", "detail": outcome.error})

    verdict = evaluate(outcome.data, _profile(profile_id))
    return _reply(200, {"extraction": outcome.data, "gate": verdict.to_item()})


def _suggest_from_resume(body: dict) -> dict:
    """Propose profile fields from a resume. Deliberately does not save.

    The user reviews and edits before committing -- a resume describes what
    someone has done, and the profile describes what they want next.
    """
    try:
        proposed = suggest_profile(
            content_b64=body.get("content_base64"),
            filename=body.get("filename", "resume.pdf"),
            text=body.get("text"),
        )
    except ResumeError as exc:
        return _reply(400, {"error": str(exc)})
    return _reply(200, {"proposed": proposed})
