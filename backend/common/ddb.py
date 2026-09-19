"""DynamoDB access helpers.

Keeps table names and the Decimal/float dance in one place so the handlers stay
readable. DynamoDB rejects floats, so numbers go in as Decimal and come back out
as int/float for JSON.
"""
from __future__ import annotations

import os
from decimal import Decimal
from typing import Any, Iterator

import boto3
from boto3.dynamodb.conditions import Key

_dynamodb = None


def _resource():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb")
    return _dynamodb


def table(name_env: str):
    return _resource().Table(os.environ[name_env])


raw_table = lambda: table("RAW_TABLE")            # noqa: E731
postings_table = lambda: table("POSTINGS_TABLE")  # noqa: E731
profiles_table = lambda: table("PROFILES_TABLE")  # noqa: E731


def to_ddb(value: Any) -> Any:
    """floats -> Decimal, and drop empty strings which DynamoDB will not index."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: to_ddb(v) for k, v in value.items() if v is not None and v != ""}
    if isinstance(value, (list, tuple)):
        return [to_ddb(v) for v in value]
    return value


def from_ddb(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, dict):
        return {k: from_ddb(v) for k, v in value.items()}
    if isinstance(value, list):
        return [from_ddb(v) for v in value]
    return value


def query_stage(stage: str, limit: int = 100) -> Iterator[dict]:
    """Walk the by-stage index for one pipeline stage's backlog."""
    tbl = postings_table()
    kwargs = {
        "IndexName": "by-stage",
        "KeyConditionExpression": Key("pipeline_stage").eq(stage),
        "Limit": limit,
    }
    while True:
        resp = tbl.query(**kwargs)
        for item in resp.get("Items", []):
            yield from_ddb(item)
        token = resp.get("LastEvaluatedKey")
        if not token:
            return
        kwargs["ExclusiveStartKey"] = token


def batch_put(tbl, items: list[dict]) -> int:
    with tbl.batch_writer(overwrite_by_pkeys=["posting_id"]) as batch:
        for item in items:
            batch.put_item(Item=to_ddb(item))
    return len(items)
