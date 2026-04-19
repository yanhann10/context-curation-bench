"""Backend selection: anthropic (direct API) or bedrock (AWS).

Env:
  XCBENCH_BACKEND = anthropic (default) | bedrock
  AWS_REGION      = us-east-1 (bedrock default)

When backend=bedrock, logical model names in the YAML are rewritten to
Bedrock inference-profile IDs via BEDROCK_MODEL_MAP.
"""
from __future__ import annotations
import os

BEDROCK_MODEL_MAP = {
    "claude-sonnet-4-6": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "claude-sonnet-4-5": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "claude-opus-4-7":   "us.anthropic.claude-sonnet-4-5-20250929-v1:0",  # fallback, Opus 4 not on Bedrock yet
    "claude-haiku-4-5":  "us.anthropic.claude-haiku-4-5-20251001-v1:0",
}


def resolve_model(name: str, backend: str) -> str:
    if backend != "bedrock":
        return name
    return BEDROCK_MODEL_MAP.get(name, name)


def make_client():
    backend = os.getenv("XCBENCH_BACKEND", "anthropic").lower()
    max_retries = int(os.getenv("XCBENCH_MAX_RETRIES", "10"))
    timeout = float(os.getenv("XCBENCH_TIMEOUT", "120"))
    if backend == "bedrock":
        from anthropic import AsyncAnthropicBedrock
        region = os.getenv("AWS_REGION", "us-east-1")
        return AsyncAnthropicBedrock(
            aws_region=region, max_retries=max_retries, timeout=timeout,
        ), backend
    from anthropic import AsyncAnthropic
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set (or set XCBENCH_BACKEND=bedrock)")
    return AsyncAnthropic(
        api_key=key, max_retries=max_retries, timeout=timeout,
    ), backend
