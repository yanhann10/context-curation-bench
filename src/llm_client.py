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
import json
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
    resp = await client.messages.create(**kwargs)
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
