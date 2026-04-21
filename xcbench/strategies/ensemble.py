"""Adapter: ensemble (parallel hierarchical + agent_managed, LLM-judged pick)."""
from __future__ import annotations

from ..registry import strategy
from xcbench._internal.strategies_hierarchical import hierarchical_build_prompt_fn
from xcbench._internal.strategies_ensemble import make_ensemble_runner


async def _get_hier_fn(ctx, corpus):
    key = ("hier_fn", id(corpus))
    if key not in ctx:
        client = ctx["client"]
        model = ctx.get("summary_model") or ctx["agent_model"]
        concurrency = max(1, int(ctx.get("concurrency", 1)))
        ctx[key] = await hierarchical_build_prompt_fn(
            client, corpus.as_legacy_list(),
            router_model=model, summary_model=model, max_ids=5,
            concurrency=concurrency,
        )
    return ctx[key]


@strategy("ensemble")
async def run(ctx, question, corpus, **_):
    client = ctx["client"]
    model = ctx["agent_model"]
    hier_fn = await _get_hier_fn(ctx, corpus)
    runner = make_ensemble_runner(hier_fn)
    answer, latency, in_tok, out_tok = await runner(
        client, question.input, corpus.as_legacy_list(), model,
    )
    return {
        "answer": answer,
        "latency_s": latency,
        "prompt_tokens": in_tok,
        "completion_tokens": out_tok,
    }
