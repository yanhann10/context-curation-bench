"""Stage 1 entry point: Full Context vs Meta-Harness-optimized curation.

Async by default — all agent/judge calls issue concurrently.

Usage:
  python main.py                 # full pipeline
  python main.py --skip-optimize # baseline spec only
  python main.py --train 4 --iter 3 --concurrency 8
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

from src.data_loader import load_all_docs, load_questions
from src.strategies import full_context, meta_harness_optimized, CurationSpec
from src.evaluator import log_results, summarize
from src.evaluator_async import run_strategy_async
from src.harness_optimizer_async import optimize_async
from src.harness_optimizer import baseline_spec


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"


async def amain(args) -> int:
    load_dotenv(ROOT / ".env")
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        print("ERROR: ANTHROPIC_API_KEY not set. Add it to .env.", file=sys.stderr)
        return 2

    agent_model = os.getenv("AGENT_MODEL", "claude-sonnet-4-6")
    judge_model = os.getenv("JUDGE_MODEL", "claude-opus-4-7")
    proposer_model = os.getenv("PROPOSER_MODEL", "claude-opus-4-7")
    concurrency = args.concurrency

    client = AsyncAnthropic(api_key=key)

    docs = load_all_docs()
    questions = load_questions()
    if not docs or not questions:
        print("ERROR: empty corpus or questions. Check data/.", file=sys.stderr)
        return 3

    n_static = sum(1 for d in docs if d['type'] == 'static')
    n_slack = sum(1 for d in docs if d['type'] == 'slack')
    print(f"Loaded {n_static} handbook docs, {n_slack} slack threads, {len(questions)} questions.")
    print(f"Agent: {agent_model}  Judge: {judge_model}  Proposer: {proposer_model}  Concurrency: {concurrency}")

    # Optimize CurationSpec
    if args.skip_optimize:
        spec = baseline_spec(docs)
        history = [{"iter": 0, "score": None, "spec": asdict(spec), "rationale": "skip-optimize"}]
        print("\n[optimize] skipped — using baseline spec")
    else:
        train_q = questions[: args.train]
        print(f"\n[optimize] train on {len(train_q)} questions, {args.iter} iterations")
        spec, history = await optimize_async(
            train_q, docs, client, agent_model, judge_model, proposer_model,
            n_iter=args.iter, concurrency=concurrency,
        )
    print(f"\n[optimize] final spec: {spec.describe()}")

    # Both strategies on full question set (run concurrently with each other).
    print("\n[run] launching both strategies concurrently")
    full_results, mh_results = await asyncio.gather(
        run_strategy_async(
            client, "full_context", full_context, questions, docs,
            agent_model, judge_model, concurrency=concurrency,
        ),
        run_strategy_async(
            client, "meta_harness_optimized",
            lambda q, d: meta_harness_optimized(q, d, spec),
            questions, docs, agent_model, judge_model, concurrency=concurrency,
        ),
    )

    all_results = full_results + mh_results

    OUTPUT_DIR.mkdir(exist_ok=True)
    log_results(all_results, OUTPUT_DIR / "results_stage1.csv")
    (OUTPUT_DIR / "optimizer_history.json").write_text(
        json.dumps(history, indent=2), encoding="utf-8"
    )
    (OUTPUT_DIR / "final_spec.json").write_text(
        json.dumps(asdict(spec), indent=2), encoding="utf-8"
    )
    summary = summarize(all_results)
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n" + "=" * 72)
    print("STAGE 1 SUMMARY")
    print("=" * 72)
    for strat, s in summary.items():
        print(f"\n  {strat}")
        for k, v in s.items():
            print(f"    {k:>22s}: {v}")

    print("\nPer-question head-to-head (quality | f1 | tokens):")
    print(f"  {'qid':<8s} {'category':<18s} "
          f"{'full_q':>6s} {'full_f1':>7s} {'full_tok':>9s} "
          f"{'mh_q':>6s} {'mh_f1':>7s} {'mh_tok':>7s}")
    by_q: dict[str, dict] = {}
    for r in all_results:
        by_q.setdefault(r.question_id, {})[r.strategy] = r
    for qid, d in by_q.items():
        fc = d.get("full_context"); m = d.get("meta_harness_optimized")
        cat = next(q["category"] for q in questions if q["id"] == qid)
        print(f"  {qid:<8s} {cat:<18s} "
              f"{fc.quality:>6.2f} {fc.f1:>7.2f} {fc.total_tokens:>9d} "
              f"{m.quality:>6.2f} {m.f1:>7.2f} {m.total_tokens:>7d}")

    print(f"\nArtifacts written under {OUTPUT_DIR}/")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-optimize", action="store_true")
    ap.add_argument("--train", type=int, default=4)
    ap.add_argument("--iter", type=int, default=3)
    ap.add_argument("--concurrency", type=int, default=8)
    args = ap.parse_args()
    return asyncio.run(amain(args))


if __name__ == "__main__":
    sys.exit(main())
