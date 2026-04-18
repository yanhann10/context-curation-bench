"""Stage 3 entry point.

Corpus:
  - handbook/*.md (timestamped 2026-01-01 uniformly — simulates stale policy)
  - data/slack_api.json (Slack-API-shape threads, validated_by_hr=true, recent)
  - data/test_questions_v2.json (10 consolidation-heavy questions)

Runs all 4 strategies. Spec is re-optimized from scratch on the v2 train set
(v1's spec was tuned to a smaller question pool). Auto-generates charts.

Usage:
  python main_stage3.py              # full pipeline + charts
  python main_stage3.py --skip-viz
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

from src.data_loader import load_all_docs, load_questions_v2
from src.strategies import full_context, meta_harness_optimized, CurationSpec
from src.evaluator import log_results, summarize
from src.evaluator_async import run_strategy_async
from src.harness_optimizer import baseline_spec
from src.harness_optimizer_async import optimize_async
from src.strategies_rag import rag_build_prompt_fn
from src.strategies_hierarchical import hierarchical_build_prompt_fn


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

    client = AsyncAnthropic(api_key=key)

    docs = load_all_docs(slack_source="api")
    questions = load_questions_v2()
    if not docs or not questions:
        print("ERROR: stage 3 data missing. Need data/slack_api.json + data/test_questions_v2.json.",
              file=sys.stderr)
        return 3

    n_static = sum(1 for d in docs if d["type"] == "static")
    n_slack = sum(1 for d in docs if d["type"] == "slack")
    cats = {}
    for q in questions:
        cats[q["category"]] = cats.get(q["category"], 0) + 1
    print(f"Loaded {n_static} handbook docs (ts=2026-01-01), {n_slack} slack-api threads, "
          f"{len(questions)} questions ({cats}).")

    # Re-optimize for Stage 3: v2 question set is different shape from v1's.
    train_q = questions[: args.train]
    print(f"\n[optimize] training on {len(train_q)} questions, {args.iter} iterations")
    spec, history = await optimize_async(
        train_q, docs, client, agent_model, judge_model, proposer_model,
        n_iter=args.iter, concurrency=concurrency,
    )
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "optimizer_history_stage3.json").write_text(
        json.dumps(history, indent=2), encoding="utf-8"
    )
    (OUTPUT_DIR / "final_spec_stage3.json").write_text(
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

    print("\n[run] launching 4 strategies concurrently")
    results_lists = await asyncio.gather(
        run_strategy_async(client, "full_context", full_context, questions, docs,
                           agent_model, judge_model, concurrency=concurrency),
        run_strategy_async(client, "meta_harness_optimized",
                           lambda q, d: meta_harness_optimized(q, d, spec),
                           questions, docs, agent_model, judge_model, concurrency=concurrency),
        run_strategy_async(client, "rag_embedding", rag_fn, questions, docs,
                           agent_model, judge_model, concurrency=concurrency),
        run_strategy_async(client, "hierarchical", hier_fn, questions, docs,
                           agent_model, judge_model, concurrency=concurrency),
    )
    all_results = [r for rs in results_lists for r in rs]

    log_results(all_results, OUTPUT_DIR / "results_stage3.csv")
    summary = summarize(all_results)
    (OUTPUT_DIR / "summary_stage3.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n" + "=" * 72)
    print("STAGE 3 SUMMARY")
    print("=" * 72)
    for strat, s in summary.items():
        print(f"\n  {strat}")
        for k, v in s.items():
            print(f"    {k:>22s}: {v}")

    # per-question grid
    strat_order = ["full_context", "meta_harness_optimized", "rag_embedding", "hierarchical"]
    print("\nPer-question × strategy quality grid:")
    print(f"  {'qid':<10s} {'category':<18s} " + " ".join(f"{s[:10]:>10s}" for s in strat_order))
    by_q: dict[str, dict] = {}
    for r in all_results:
        by_q.setdefault(r.question_id, {})[r.strategy] = r
    for qid in sorted(by_q.keys()):
        d = by_q[qid]
        cat = next(q["category"] for q in questions if q["id"] == qid)
        row = f"  {qid:<10s} {cat:<18s} "
        for s in strat_order:
            row += f"{d[s].quality:>10.2f} " if s in d else f"{'--':>10s} "
        print(row)

    # Charts
    if not args.skip_viz:
        try:
            from src import viz
            viz.plot_quality_vs_cost(OUTPUT_DIR / "results_stage3.csv",
                                     OUTPUT_DIR / "chart_stage3.png")
            viz.plot_heatmap(OUTPUT_DIR / "results_stage3.csv",
                             OUTPUT_DIR / "chart_stage3_heatmap.png")
        except Exception as e:
            print(f"[viz] skipped: {e}")

    print(f"\nArtifacts under {OUTPUT_DIR}/")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=int, default=5, help="optimizer train-set size")
    ap.add_argument("--iter", type=int, default=3)
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--rag-k", type=int, default=6)
    ap.add_argument("--hier-ids", type=int, default=5)
    ap.add_argument("--skip-viz", action="store_true")
    args = ap.parse_args()
    return asyncio.run(amain(args))


if __name__ == "__main__":
    sys.exit(main())
