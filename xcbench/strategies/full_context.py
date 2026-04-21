"""Adapter: full-context strategy. Stuff all corpus docs into the prompt."""
from __future__ import annotations

from ..registry import strategy
from xcbench._internal.strategies import full_context as _full_context  # reuse existing


@strategy("full_context")
async def run(ctx, question, corpus, **params):
    """Return a prompt string. The runner handles answer + judge."""
    return _full_context(question.input, corpus.as_legacy_list())
