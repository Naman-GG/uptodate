"""Model-agnostic structured output via the Bedrock Converse API.

Why this exists rather than the Anthropic Messages endpoint: Anthropic models on
Bedrock are sold through AWS Marketplace, and Marketplace subscriptions require
a credit card that not every account can provide. The subscription fails with
INVALID_PAYMENT_INSTRUMENT and no amount of retrying fixes it -- it is a known
AWS-side loop that only clears through support escalation.

Converse is the cross-model API, and models AWS serves directly (Amazon Nova,
OpenAI's open-weight gpt-oss) bypass Marketplace entirely. Writing against
Converse rather than one vendor's endpoint means the model is a configuration
value, not an architectural commitment -- including switching back to Claude if
the Marketplace subscription ever completes.

Structured output is obtained by declaring a single tool whose input schema is
the shape we want, then forcing the model to call it. Every candidate model
(nova-2-lite, nova-pro, nova-lite, gpt-oss-120b, gpt-oss-20b) supports forced
tool choice, which is what makes this portable.
"""
from __future__ import annotations

import functools
import logging
import os
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.config import Config

log = logging.getLogger(__name__)

AWS_REGION = os.environ.get("BEDROCK_REGION", os.environ.get("AWS_REGION", "us-east-1"))

# Cheap model, runs on every screened posting -- it sets the bill.
EXTRACT_MODEL = os.environ.get("EXTRACT_MODEL", "us.amazon.nova-2-lite-v1:0")
# Stronger model, runs only on postings that cleared the gate.
SCORE_MODEL = os.environ.get("SCORE_MODEL", "us.amazon.nova-pro-v1:0")

TOOL_NAME = "record_fields"


@functools.lru_cache(maxsize=1)
def client():
    """One client per warm container. Retries are handled by botocore."""
    return boto3.client(
        "bedrock-runtime",
        region_name=AWS_REGION,
        config=Config(retries={"max_attempts": 4, "mode": "adaptive"}, read_timeout=120),
    )


@dataclass
class ConverseResult:
    ok: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    usage: dict[str, int] | None = None


def answer_text(response: dict) -> str:
    """Pull the assistant's prose out of a Converse response.

    Reasoning models (gpt-oss, and Nova with reasoning enabled) emit a
    `reasoningContent` block *before* the answer, so indexing content[0] returns
    the chain of thought -- or raises KeyError. Walk the blocks instead.
    """
    for block in response.get("output", {}).get("message", {}).get("content", []):
        if "text" in block:
            return block["text"]
    return ""


def tool_input(response: dict) -> dict[str, Any] | None:
    for block in response.get("output", {}).get("message", {}).get("content", []):
        if "toolUse" in block:
            return block["toolUse"].get("input")
    return None


def structured(
    *,
    system: str,
    user: str,
    schema: dict[str, Any],
    model: str | None = None,
    max_tokens: int = 1500,
) -> ConverseResult:
    """One call, one object out. No agent loop -- this is a pure transform."""
    model_id = model or EXTRACT_MODEL
    tool_config = {
        "tools": [
            {
                "toolSpec": {
                    "name": TOOL_NAME,
                    "description": "Record the extracted fields for this posting.",
                    "inputSchema": {"json": schema},
                }
            }
        ],
        # Forcing the call is what guarantees structure. Without it the model may
        # answer in prose and we are back to parsing JSON out of a code fence.
        "toolChoice": {"tool": {"name": TOOL_NAME}},
    }

    try:
        response = client().converse(
            modelId=model_id,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            inferenceConfig={"maxTokens": max_tokens, "temperature": 0},
            toolConfig=tool_config,
        )
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller for quarantine
        return ConverseResult(False, error=f"{type(exc).__name__}: {exc}")

    usage = response.get("usage") or {}
    parsed = tool_input(response)
    if parsed is None:
        return ConverseResult(
            False,
            error=f"model returned no tool call (stopReason={response.get('stopReason')})",
            usage=_usage(usage),
        )
    return ConverseResult(True, data=parsed, usage=_usage(usage))


def _usage(u: dict) -> dict[str, int]:
    return {
        "input_tokens": u.get("inputTokens", 0),
        "output_tokens": u.get("outputTokens", 0),
        "total_tokens": u.get("totalTokens", 0),
    }
