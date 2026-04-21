"""Thin async Claude wrapper with prompt-caching helpers.

Two helpers:
  - complete_text(system, user, model, max_tokens)  -> (text, in_tok, out_tok, latency_s)
  - complete_json(system, user, model, max_tokens)  -> (dict, in_tok, out_tok, latency_s)

complete_json uses assistant-prefill to force JSON output (no native
response_format on Claude; prefill '{' works reliably).

System prompts can be passed as a list of Anthropic content blocks to use
prompt caching, or as a plain string (we wrap with cache_control automatically).
"""
from __future__ import annotations
import asyncio
import json
import os
import random
import re
import time
from typing import Union

from anthropic import AsyncAnthropic


# Per-model pricing (USD per 1M tokens), Apr 2026.
PRICE = {
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-7": (15.00, 75.00),
    "claude-haiku-4-5": (0.25, 1.25),
    # long-context fallbacks if env uses the [1m] variants
    "claude-sonnet-4-6[1m]": (3.00, 15.00),
    "claude-opus-4-7[1m]": (15.00, 75.00),
    # Bedrock IDs — same token prices as Anthropic direct API
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0": (3.00, 15.00),
    "us.anthropic.claude-haiku-4-5-20251001-v1:0": (1.00, 5.00),
}


def cost_usd(model: str, in_tok: int, out_tok: int) -> float:
    pin, pout = PRICE.get(model, (3.00, 15.00))
    return in_tok * pin / 1_000_000 + out_tok * pout / 1_000_000


def _system_blocks(system: Union[str, list, None]):
    """Always return list-of-blocks so we can add cache_control on the last."""
    if system is None:
        return None
    if isinstance(system, str):
        return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
    return system


def _is_retryable_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code in {408, 409, 429, 500, 502, 503, 504}:
        return True
    text = str(exc).lower()
    return any(
        token in text
        for token in (
            "429",
            "too many requests",
            "rate limit",
            "throttl",
            "overloaded",
            "service unavailable",
            "timed out",
            "timeout",
            "connection reset",
        )
    )


async def create_message(client: AsyncAnthropic, **kwargs):
    attempts = max(1, int(os.getenv("XCBENCH_API_RETRY_ATTEMPTS", os.getenv("XCBENCH_MAX_RETRIES", "10"))))
    backoff_base = float(os.getenv("XCBENCH_BACKOFF_BASE", "1.5"))
    backoff_max = float(os.getenv("XCBENCH_BACKOFF_MAX", "30"))
    for attempt in range(1, attempts + 1):
        try:
            return await client.messages.create(**kwargs)
        except Exception as e:
            if attempt >= attempts or not _is_retryable_error(e):
                raise
            sleep_s = min(backoff_max, backoff_base * (2 ** (attempt - 1)))
            sleep_s *= 0.8 + random.random() * 0.4
            await asyncio.sleep(sleep_s)


async def complete_text(
    client: AsyncAnthropic,
    user: str,
    system: Union[str, list, None] = None,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 1024,
    temperature: float = 0.0,
) -> tuple[str, int, int, float]:
    kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[{"role": "user", "content": user}],
    )
    blocks = _system_blocks(system)
    if blocks is not None:
        kwargs["system"] = blocks
    t0 = time.time()
    resp = await create_message(client, **kwargs)
    latency = time.time() - t0
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    u = resp.usage
    return text, u.input_tokens, u.output_tokens, latency


async def complete_json(
    client: AsyncAnthropic,
    user: str,
    system: Union[str, list, None] = None,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 1024,
    temperature: float = 0.0,
) -> tuple[dict, int, int, float]:
    """Request JSON output; parse leniently.

    Some Claude 4.x variants reject assistant-prefill, so we rely on strict
    JSON instruction in the system prompt (callers already include it) plus
    _safe_json regex-extract fallback.
    """
    reinforced_user = user + "\n\nReturn a single JSON object. No prose, no code fences."
    text, in_tok, out_tok, latency = await complete_text(
        client, user=reinforced_user, system=system,
        model=model, max_tokens=max_tokens, temperature=temperature,
    )
    data = _safe_json(text)
    return data, in_tok, out_tok, latency


def _safe_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return {}
        try:
            return json.loads(m.group(0))
        except Exception:
            return {}
