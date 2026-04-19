"""Adapter: meta-harness-inspired typed-spec strategy.

When called without a fitted spec, uses the baseline spec (all docs).
When the suite has an `optimize:` block, the optimizer fits a spec on a
train subset and the runner passes it in via ctx['fitted_spec'].
"""
from __future__ import annotations

from ..registry import strategy
from src.strategies import meta_harness_optimized
from src.harness_optimizer import baseline_spec


@strategy("meta_harness")
async def run(ctx, question, corpus, **_):
    docs_legacy = corpus.as_legacy_list()
    spec = ctx.get("fitted_spec") or baseline_spec(docs_legacy)
    return meta_harness_optimized(question.input, docs_legacy, spec)
