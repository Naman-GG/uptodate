"""Bedrock client factory.

Uses the Mantle client (the Messages-API Bedrock endpoint) rather than the
legacy bedrock-runtime InvokeModel path, which is what gives us structured
outputs and prompt caching -- both GA on Bedrock and both load-bearing here.

Model IDs on Bedrock carry an `anthropic.` prefix. They are read from the
environment so a region without a given model can be worked around without a
code change.
"""
from __future__ import annotations

import functools
import os

from anthropic import AnthropicBedrockMantle

AWS_REGION = os.environ.get("BEDROCK_REGION", os.environ.get("AWS_REGION", "us-east-1"))

# Cheap model: runs once per posting, so its per-token cost sets the bill.
EXTRACT_MODEL = os.environ.get("EXTRACT_MODEL", "anthropic.claude-haiku-4-5")
# Stronger model: runs only on postings that already cleared the gate.
SCORE_MODEL = os.environ.get("SCORE_MODEL", "anthropic.claude-sonnet-5")


@functools.lru_cache(maxsize=1)
def client() -> AnthropicBedrockMantle:
    """One client per warm Lambda container; the SDK is thread-safe and pools connections."""
    return AnthropicBedrockMantle(aws_region=AWS_REGION, max_retries=3, timeout=60.0)
