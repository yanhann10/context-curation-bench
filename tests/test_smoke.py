"""Smoke tests — no network, no Anthropic key required.

Covers:
  - frontier.compute Pareto math
  - suite YAMLs parse + validate against the registry
  - decorator registries are populated by built-ins
"""
from __future__ import annotations

import pytest

from xcbench import frontier
from xcbench.spec import load_suite, validate
from xcbench.registry import STRATEGIES, GRADERS, CORPUS_LOADERS
from xcbench.dataset import Question, validate_questions


def test_registries_populated_by_builtins():
    # importing xcbench.cli triggers registration of strategies + judge
    import xcbench.cli  # noqa: F401
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


def test_question_validation_accepts_resolved_and_ambiguous_shapes():
    resolved = Question(
        id="q-ok",
        input="question",
        golden="answer",
        category="resolved_conflict",
        relevant_doc_ids=["a", "b"],
        canonical_source_ids=["b"],
        gold_status="resolved",
    )
    ambiguous = Question(
        id="q-amb",
        input="question",
        golden="The provided sources do not resolve this conflict.",
        acceptable_answers=["I can't determine the answer from the provided sources."],
        category="abstain_required",
        relevant_doc_ids=["a", "b"],
        gold_status="ambiguous",
        abstain_expected=True,
    )
    assert validate_questions([resolved, ambiguous]) == []


def test_question_validation_rejects_missing_canonical_or_bad_ambiguous_config():
    bad_resolved = Question(
        id="q-bad-1",
        input="question",
        golden="answer",
        gold_status="resolved",
    )
    bad_ambiguous = Question(
        id="q-bad-2",
        input="question",
        golden="answer",
        gold_status="ambiguous",
        abstain_expected=False,
    )
    errs = validate_questions([bad_resolved, bad_ambiguous])
    assert any("canonical_source_ids" in e for e in errs)
    assert any("abstain_expected=true" in e for e in errs)


@pytest.mark.parametrize("suite_path", [
    "suites/sample_data_hr_policy.yaml",
    "examples/toy/suite.yaml",
])
def test_suite_parses_and_validates(suite_path):
    import xcbench.cli  # noqa: F401  register built-ins
    spec = load_suite(suite_path)
    errs = validate(spec)
    assert errs == [], f"{suite_path} did not validate: {errs}"
    assert spec.strategies, "suite should declare at least one strategy"
    assert spec.frontier.axes and spec.frontier.direction


def test_run_matrix_end_to_end_with_mock_strategy():
    """Exercise the full matrix runner without hitting the network.

    Registers a mock strategy + grader, builds a minimal Question and an
    empty corpus, runs `run_matrix`, and asserts the shape of results and
    summarize() output. This is the regression guard for the earlier
    "CI only import-checks" gap: any bug in runner/summarize flow now fails
    in CI before a live eval burns API budget.
    """
    import asyncio
    from types import SimpleNamespace

    from xcbench.dataset import Question
    from xcbench.registry import strategy, grader
    from xcbench.runner import run_matrix, summarize

    @strategy("_test_echo")
    async def _echo(ctx, question, corpus, **_):
        return {
            "answer": f"echo: {question.input}",
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "latency_s": 0.001,
        }

    @grader("_test_pass")
    async def _pass(ctx, question, answer: str) -> dict:
        return {
            "quality": 1.0 if answer.startswith("echo:") else 0.0,
            "note": "mock-grader",
            "judge_prompt_tokens": 0,
            "judge_completion_tokens": 0,
        }

    questions = [
        Question(id="q1", input="hello", golden="echo: hello", category="t"),
        Question(id="q2", input="world", golden="echo: world", category="t"),
    ]
    corpus = SimpleNamespace(docs=[], as_legacy_list=lambda: [])
    strategies = [SimpleNamespace(name="_test_echo", params={})]
    ctx = {
        "client": None,
        "agent_model": "mock",
        "judge_model": "mock",
        "grader_name": "_test_pass",
    }

    results = asyncio.run(run_matrix(ctx, strategies, questions, corpus, concurrency=1))
    assert len(results) == 2, f"expected 2 cells, got {len(results)}"
    assert all(r.quality == 1.0 for r in results), \
        f"mock grader should pass; got {[r.quality for r in results]}"
    assert all(r.strategy == "_test_echo" for r in results)
    assert all(r.answer.startswith("echo:") for r in results)
    assert all(r.total_tokens == 15 for r in results)

    summary = summarize(results)
    assert "_test_echo" in summary
    row = summary["_test_echo"]
    assert row["n"] == 2
    assert row["quality_mean"] == 1.0
    assert row["prompt_tokens_mean"] == 10
    assert "quality_by_category" in row and row["quality_by_category"].get("t") == 1.0


def test_no_hardcoded_domain_persona_in_prompts():
    """Guard against the cross-domain portability bug.

    Strategy and question-gen prompts must not hardcode the HR/GitLab
    persona. Banned tokens are the ones that caused agent_managed to
    refuse q-polars-009 ("not GitLab HR"). If you add a new domain-specific
    prompt, take a `domain_description` parameter instead.
    """
    import pathlib
    banned = ["New Hire Onboarding", "GitLab team", "GitLab New Hire"]
    files = [
        "src/strategies.py",
        "src/strategies_hierarchical.py",
        "src/strategies_rag.py",
        "src/strategies_agent_managed.py",
        "src/strategies_harness.py",
        "src/strategies_cascade.py",
        "src/strategies_ensemble.py",
        "src/harness_optimizer.py",
        "src/harness_optimizer_async.py",
        "xcbench/expand_questions.py",
    ]
    root = pathlib.Path(__file__).parent.parent
    offenders = []
    for rel in files:
        p = root / rel
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        for b in banned:
            if b in text:
                offenders.append(f"{rel}: contains banned token {b!r}")
    assert not offenders, (
        "Hardcoded domain persona found — strategy/gen prompts must stay "
        "domain-agnostic:\n  " + "\n  ".join(offenders)
    )
