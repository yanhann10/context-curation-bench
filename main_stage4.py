"""Stage 4 entry point — 7-strategy eval on Polars Python library Q&A.

Second-domain test: does the Stage 3 finding (agent_managed best single,
ensemble matches full_context at 64% cost, cascade broken) generalize from
HR policy QA to Polars technical QA?

Corpus:
  - data/polars/docs/*.md   — 12-13 user-guide pages, timestamped 2026-01-01
  - data/polars/slack_api.json — 10 GitHub-discussion threads (5 contradict
    deprecations, 3 extend, 2 confirm)
  - data/polars/test_questions.json — 10 Qs (4 slack_contradicts/deprecation,
    2 slack_only, 2 needs_both, 2 docs_only)

Uses existing Stage 3 strategy stack verbatim — only the data source changes.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv
from anthropic import AsyncAnthropic

from src.data_loader import load_polars_all, load_polars_questions
from src.strategies import full_context, meta_harness_optimized, CurationSpec
from src.evaluator import log_results, summarize
from src.evaluator_async import run_strategy_async, run_agent_strategy_async
from src.harness_optimizer import baseline_spec
from src.harness_optimizer_async import optimize_async
from src.strategies_rag import rag_build_prompt_fn
from src.strategies_hierarchical import hierarchical_build_prompt_fn
from src.strategies_agent_managed import agent_managed_runner
from src.strategies_cascade import make_cascade_runner
from src.strategies_ensemble import make_ensemble_runner


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"


async def amain(args) -> int:
    load_dotenv(ROOT / ".env")
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        print("ERROR: ANTHROPIC_API_KEY not set.", file=sys.stderr)
        return 2

    agent_model = os.getenv("AGENT_MODEL", "claude-sonnet-4-6")
    judge_model = os.getenv("JUDGE_MODEL", "claude-sonnet-4-6")
    proposer_model = os.getenv("PROPOSER_MODEL", "claude-sonnet-4-6")
    summary_model = os.getenv("SUMMARY_MODEL", "claude-sonnet-4-6")
    router_model = os.getenv("ROUTER_MODEL", "claude-sonnet-4-6")
    concurrency = args.concurrency

    client = AsyncAnthropic(api_key=key, max_retries=6, timeout=120.0)

    docs = load_polars_all()
    questions = load_polars_questions()
    if not docs or not questions:
        print("ERROR: data/polars/ is missing docs or test_questions.", file=sys.stderr)
        return 3

    n_static = sum(1 for d in docs if d["type"] == "static")
    n_slack = sum(1 for d in docs if d["type"] == "slack")
    cats: dict[str, int] = {}
    for q in questions:
        cats[q["category"]] = cats.get(q["category"], 0) + 1
    print(f"Stage 4 (Polars): {n_static} doc pages + {n_slack} gh-discussion threads, "
          f"{len(questions)} questions ({cats}).")

    # Optimize spec from scratch on Polars train set.
    train_q = questions[: args.train]
    print(f"\n[optimize] training on {len(train_q)} questions, {args.iter} iterations")
    spec, history = await optimize_async(
        train_q, docs, client, agent_model, judge_model, proposer_model,
        n_iter=args.iter, concurrency=concurrency,
    )
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "optimizer_history_stage4.json").write_text(
        json.dumps(history, indent=2), encoding="utf-8"
    )
    (OUTPUT_DIR / "final_spec_stage4.json").write_text(
        json.dumps(asdict(spec), indent=2), encoding="utf-8"
    )
    print(f"[spec] {spec.describe()}")

    print("\n[rag] building embedding index")
    rag_fn = await rag_build_prompt_fn(client, docs, k=args.rag_k)
    print("[hier] summarizing + caching")
    hier_fn = await hierarchical_build_prompt_fn(
        client, docs, router_model=router_model, summary_model=summary_model,
        max_ids=args.hier_ids,
    )
    cascade_runner = make_cascade_runner(hier_fn, final_fallback="full")
    ensemble_runner = make_ensemble_runner(hier_fn)

    all_results = []

    # Phase 1: 5 base strategies concurrent
    print("\n[run] phase 1/3 — 5 base strategies")
    phase1 = await asyncio.gather(
        run_strategy_async(client, "full_context", full_context, questions, docs,
                           agent_model, judge_model, concurrency=concurrency),
        run_strategy_async(client, "meta_harness_optimized",
                           lambda q, d: meta_harness_optimized(q, d, spec),
                           questions, docs, agent_model, judge_model, concurrency=concurrency),
        run_strategy_async(client, "rag_embedding", rag_fn, questions, docs,
                           agent_model, judge_model, concurrency=concurrency),
        run_strategy_async(client, "hierarchical", hier_fn, questions, docs,
                           agent_model, judge_model, concurrency=concurrency),
        run_agent_strategy_async(client, "agent_managed", agent_managed_runner,
                                 questions, docs, agent_model, judge_model, concurrency=3),
    )
    for rs in phase1:
        all_results.extend(rs)

    print("[run] phase 2/3 — cascade_router")
    all_results.extend(await run_agent_strategy_async(
        client, "cascade_router", cascade_runner, questions, docs,
        agent_model, judge_model, concurrency=2,
    ))

    print("[run] phase 3/3 — ensemble")
    all_results.extend(await run_agent_strategy_async(
        client, "ensemble", ensemble_runner, questions, docs,
        agent_model, judge_model, concurrency=2,
    ))

    log_results(all_results, OUTPUT_DIR / "results_stage4.csv")
    summary = summarize(all_results)
    (OUTPUT_DIR / "summary_stage4.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    print("\n" + "=" * 72)
    print("STAGE 4 SUMMARY (Polars domain)")
    print("=" * 72)
    for strat, s in summary.items():
        print(f"\n  {strat}")
        for k, v in s.items():
            print(f"    {k:>22s}: {v}")

    # per-question grid
    strat_order = ["full_context", "meta_harness_optimized", "rag_embedding",
                   "hierarchical", "agent_managed", "cascade_router", "ensemble"]
    print("\nPer-question × strategy quality grid:")
    print(f"  {'qid':<12s} {'category':<20s}" + " ".join(f"{s[:11]:>11s}" for s in strat_order))
    by_q: dict[str, dict] = {}
    for r in all_results:
        by_q.setdefault(r.question_id, {})[r.strategy] = r
    for qid in sorted(by_q.keys()):
        d = by_q[qid]
        cat = next(q["category"] for q in questions if q["id"] == qid)
        row = f"  {qid:<12s} {cat:<20s}"
        for s in strat_order:
            row += f"{d[s].quality:>11.2f}" if s in d else f"{'--':>11s}"
        print(row)

    if not args.skip_viz:
        try:
            from src import viz
            viz.plot_quality_vs_cost(OUTPUT_DIR / "results_stage4.csv",
                                     OUTPUT_DIR / "chart_stage4.png")
            viz.plot_heatmap(OUTPUT_DIR / "results_stage4.csv",
                             OUTPUT_DIR / "chart_stage4_heatmap.png")
        except Exception as e:
            print(f"[viz] skipped: {e}")

    print(f"\nArtifacts under {OUTPUT_DIR}/")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=int, default=5)
    ap.add_argument("--iter", type=int, default=2)
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--rag-k", type=int, default=6)
    ap.add_argument("--hier-ids", type=int, default=5)
    ap.add_argument("--skip-viz", action="store_true")
    args = ap.parse_args()
    return asyncio.run(amain(args))


if __name__ == "__main__":
    sys.exit(main())
