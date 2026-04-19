"""Smoke tests — no network, no Anthropic key required.

Covers:
  - frontier.compute Pareto math
  - suite YAMLs parse + validate against the registry
  - decorator registries are populated by built-ins
"""
from __future__ import annotations

import pytest

from ccbench import frontier
from ccbench.spec import load_suite, validate
from ccbench.registry import STRATEGIES, GRADERS, CORPUS_LOADERS


def test_registries_populated_by_builtins():
    # importing ccbench.cli triggers registration of strategies + judge
    import ccbench.cli  # noqa: F401
    for s in ("full_context", "rag_embedding", "hierarchical",
              "agent_managed", "ensemble", "meta_harness"):
        assert s in STRATEGIES, f"built-in strategy '{s}' not registered"
    assert "llm_judge" in GRADERS
    assert "jsonl" in CORPUS_LOADERS


def test_frontier_compute_basic():
    summary = {
        "cheap_but_bad": {"quality_mean": 0.5, "cost_usd_total": 0.01, "total_tokens_mean": 100},
        "balanced":      {"quality_mean": 0.9, "cost_usd_total": 0.10, "total_tokens_mean": 2000},
        "expensive_pro": {"quality_mean": 0.95, "cost_usd_total": 0.50, "total_tokens_mean": 20000},
        "dominated":     {"quality_mean": 0.8, "cost_usd_total": 0.60, "total_tokens_mean": 30000},
    }
    report = frontier.compute(
        summary,
        axes=["quality", "cost_usd", "total_tokens"],
        direction=["max", "min", "min"],
    )
    assert "dominated" in report["dominated"], "strictly-dominated strategy should be flagged"
    assert set(report["frontier"]) == {"cheap_but_bad", "balanced", "expensive_pro"}
    assert report["per_axis_best"]["quality"] == "expensive_pro"
    assert report["per_axis_best"]["cost_usd"] == "cheap_but_bad"
    assert report["per_axis_best"]["total_tokens"] == "cheap_but_bad"


def test_frontier_render_has_axes_and_winners():
    summary = {"a": {"quality_mean": 1.0, "cost_usd_total": 0.0, "total_tokens_mean": 0}}
    report = frontier.compute(summary, ["quality", "cost_usd"], ["max", "min"])
    out = frontier.render(report, ["quality", "cost_usd"])
    assert "Pareto frontier" in out
    assert "a" in out


@pytest.mark.parametrize("suite_path", [
    "suites/sample_data_hr_policy.yaml",
    "examples/toy/suite.yaml",
])
def test_suite_parses_and_validates(suite_path):
    import ccbench.cli  # noqa: F401  register built-ins
    spec = load_suite(suite_path)
    errs = validate(spec)
    assert errs == [], f"{suite_path} did not validate: {errs}"
    assert spec.strategies, "suite should declare at least one strategy"
    assert spec.frontier.axes and spec.frontier.direction
