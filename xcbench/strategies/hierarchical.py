"""Adapter: hierarchical (summarize -> route -> expand)."""
from __future__ import annotations

from ..registry import strategy
from xcbench._internal.strategies_hierarchical import (
    summarize_all, route_docs, hierarchical_prompt,
)


@strategy("hierarchical")
async def run(ctx, question, corpus, *, max_ids: int = 5, **_):
    client = ctx["client"]
    summary_model = ctx.get("summary_model") or ctx["agent_model"]
    router_model = ctx.get("router_model") or ctx["agent_model"]
    concurrency = max(1, int(ctx.get("concurrency", 1)))

    docs_legacy = corpus.as_legacy_list()
    cache_key = ("summaries", id(corpus), summary_model)
    if cache_key not in ctx:
        ctx[cache_key] = await summarize_all(
            client,
            docs_legacy,
            summary_model,
            concurrency=concurrency,
        )
    summaries = ctx[cache_key]

    ids = await route_docs(
        client, question.input, summaries, docs_legacy, router_model, max_ids=max_ids,
    )
    by_id = {d["id"]: d for d in docs_legacy}
    selected = [by_id[i] for i in ids if i in by_id]
    return hierarchical_prompt(question.input, selected)
