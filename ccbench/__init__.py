"""ccbench — a barebones context-curation benchmark.

Shape borrowed from letta-evals (YAML suite, JSONL data, decorator registry,
runner CLI). Four things that are novel to this bench:

  1. `strategies:` is a list — a suite IS a matrix, not a single target.
  2. `CorpusSpec` is typed separately from the question set: docs carry
     kind (static|fresh), timestamp, freshness_priority.
  3. `frontier:` gate reports a Pareto set over (quality, cost, tokens)
     instead of a single pass/fail threshold.
  4. `optimize:` is a built-in phase — propose → evaluate → keep-best over
     a typed StrategySpec, run before final scoring.
"""
from .registry import strategy, grader, corpus_loader, STRATEGIES, GRADERS, CORPUS_LOADERS
from . import corpus  # register jsonl loader
from . import judge  # register llm_judge grader
from . import strategies  # register built-in strategies

__all__ = ["strategy", "grader", "corpus_loader", "STRATEGIES", "GRADERS", "CORPUS_LOADERS"]
