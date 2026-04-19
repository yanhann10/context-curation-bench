"""Adapter: agent-managed (tool-use loop).

Returns a pre-scored partial result — the runner skips the answer step
when a strategy returns a dict rather than a string.
"""
from __future__ import annotations

from ..registry import strategy
from src.strategies_agent_managed import agent_managed_runner


@strategy("agent_managed")
async def run(ctx, question, corpus, *, max_iter: int = 6, **_):
    client = ctx["client"]
    model = ctx["agent_model"]
    answer, latency, in_tok, out_tok = await agent_managed_runner(
        client, question.input, corpus.as_legacy_list(), model, max_iter=max_iter,
    )
    return {
        "answer": answer,
        "latency_s": latency,
        "prompt_tokens": in_tok,
        "completion_tokens": out_tok,
    }
