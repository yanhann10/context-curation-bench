"""Adapter: thick harness — plan → execute → verify (optional refine).

Tests the thick end of the harness axis. Plan is a JSON sketch of
sub_questions + likely_handbook_topics + likely_slack_topics + risks.
Verify emits {unverified_claims, needs_more_fetch}; if true, one refine pass.
"""
from __future__ import annotations

from ..registry import strategy
from src.strategies_harness import thick_harness_runner


@strategy("thick_harness")
async def run(ctx, question, corpus, *, max_iter: int = 5, **_):
    client = ctx["client"]
    model = ctx["agent_model"]
    answer, latency, in_tok, out_tok = await thick_harness_runner(
        client, question.input, corpus.as_legacy_list(), model, max_iter=max_iter,
    )
    return {
        "answer": answer,
        "latency_s": latency,
        "prompt_tokens": in_tok,
        "completion_tokens": out_tok,
    }
