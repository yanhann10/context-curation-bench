"""Adapter: thin harness — bare tool loop, minimal system, low max_iter.

Same 4 tools as agent_managed; tests the thin end of the harness axis.
"""
from __future__ import annotations

from ..registry import strategy
from xcbench._internal.strategies_harness import thin_harness_runner


@strategy("thin_harness")
async def run(ctx, question, corpus, *, max_iter: int = 3, **_):
    client = ctx["client"]
    model = ctx["agent_model"]
    answer, latency, in_tok, out_tok = await thin_harness_runner(
        client, question.input, corpus.as_legacy_list(), model, max_iter=max_iter,
    )
    return {
        "answer": answer,
        "latency_s": latency,
        "prompt_tokens": in_tok,
        "completion_tokens": out_tok,
    }
