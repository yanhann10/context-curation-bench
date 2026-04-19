"""Built-in propose/evaluate/keep-best loop over a typed StrategySpec.

This is the `optimize:` phase — run before the full matrix. Currently
supports `meta_harness` (typed CurationSpec). Adding other optimizable
strategies is a matter of wiring a new (baseline, propose, score) trio.
"""
from __future__ import annotations
import asyncio

from src.harness_optimizer_async import optimize_async


async def fit(ctx, strategy_name: str, train_questions, corpus, *, iterations: int = 3):
    if strategy_name != "meta_harness":
        raise ValueError(f"optimize not implemented for strategy '{strategy_name}'")

    client = ctx["client"]
    docs_legacy = corpus.as_legacy_list()
    train_legacy = [q.as_legacy_dict() for q in train_questions]

    spec, history = await optimize_async(
        train_legacy,
        docs_legacy,
        client,
        agent_model=ctx["agent_model"],
        judge_model=ctx.get("judge_model", "claude-opus-4-7"),
        proposer_model=ctx.get("proposer_model", "claude-opus-4-7"),
        n_iter=iterations,
        concurrency=ctx.get("concurrency", 8),
    )
    return spec, history
