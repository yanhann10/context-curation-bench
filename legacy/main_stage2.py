"""Stage 2 entry point: run all strategies side-by-side.

Strategies:
  - full_context  (baseline, Stage 1)
  - meta_harness_optimized  (Stage 1, uses saved final_spec if present, else optimize)
  - rag_embedding  (top-k over text-embedding-3-small)
  - hierarchical   (summarize-then-route)

Usage:
  python main_stage2.py                 # run all 4 strategies
  python main_stage2.py --rag-k 6
  python main_stage2.py --hier-ids 5
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

# repo-root shim so `python legacy/main_stage2.py` resolves `from src...`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from anthropic import AsyncAnthropic

from src.data_loader import load_all_docs, load_questions
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
    judge_model = os.getenv("JUDGE_MODEL", "claude-opus-4-7")
    proposer_model = os.getenv("PROPOSER_MODEL", "claude-opus-4-7")
    summary_model = os.getenv("SUMMARY_MODEL", "claude-haiku-4-5")
    router_model = os.getenv("ROUTER_MODEL", "claude-haiku-4-5")
    concurrency = args.concurrency

    client = AsyncAnthropic(api_key=key)
    docs = load_all_docs()
    questions = load_questions()
    if not docs or not questions:
        print("ERROR: empty corpus. Check data/.", file=sys.stderr)
        return 3

    n_static = sum(1 for d in docs if d['type'] == 'static')
    n_slack = sum(1 for d in docs if d['type'] == 'slack')
    print(f"Loaded {n_static} handbook docs, {n_slack} slack threads, {len(questions)} questions.")

    # --- Stage 1 spec: reuse if saved, else optimize ---
    saved_spec_path = OUTPUT_DIR / "final_spec.json"
    if saved_spec_path.exists() and not args.reoptimize:
        data = json.loads(saved_spec_path.read_text())
        spec = CurationSpec(**{k: v for k, v in data.items() if k in CurationSpec.__dataclass_fields__})
        print(f"\n[spec] reusing saved: {spec.describe()}")
    else:
        train_q = questions[: args.train]
        print(f"\n[spec] optimizing on {len(train_q)} train questions")
        spec, history = await optimize_async(
            train_q, docs, client, agent_model, judge_model, proposer_model,
            n_iter=args.iter, concurrency=concurrency,
        )
        OUTPUT_DIR.mkdir(exist_ok=True)
        (OUTPUT_DIR / "optimizer_history.json").write_text(
            json.dumps(history, indent=2), encoding="utf-8"
        )
        (OUTPUT_DIR / "final_spec.json").write_text(
            json.dumps(asdict(spec), indent=2), encoding="utf-8"
        )
        print(f"[spec] optimized: {spec.describe()}")

    # --- Build prompt fns for RAG + hierarchical (these do preprocessing once) ---
    print("\n[rag] building embedding index")
    rag_fn = await rag_build_prompt_fn(client, docs, k=args.rag_k)
    print("[hier] summarizing + caching")
    hier_fn = await hierarchical_build_prompt_fn(
        client, docs, router_model=router_model, summary_model=summary_model,
        max_ids=args.hier_ids,
    )

    # --- Run all 4 strategies concurrently ---
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

    OUTPUT_DIR.mkdir(exist_ok=True)
    log_results(all_results, OUTPUT_DIR / "results_stage2.csv")
    summary = summarize(all_results)
    (OUTPUT_DIR / "summary_stage2.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    print("\n" + "=" * 72)
    print("STAGE 2 SUMMARY")
    print("=" * 72)
    for strat, s in summary.items():
        print(f"\n  {strat}")
        for k, v in s.items():
            print(f"    {k:>22s}: {v}")

    print("\nPer-question × strategy quality grid:")
    strat_order = ["full_context", "meta_harness_optimized", "rag_embedding", "hierarchical"]
    header = f"  {'qid':<8s} {'category':<18s} " + " ".join(f"{s[:10]:>10s}" for s in strat_order)
    print(header)
    by_q: dict[str, dict] = {}
    for r in all_results:
        by_q.setdefault(r.question_id, {})[r.strategy] = r
    for qid, d in by_q.items():
        cat = next(q["category"] for q in questions if q["id"] == qid)
        row = f"  {qid:<8s} {cat:<18s} "
        for s in strat_order:
            row += f"{d[s].quality:>10.2f} " if s in d else f"{'--':>10s} "
        print(row)

    print(f"\nArtifacts written under {OUTPUT_DIR}/")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=int, default=4)
    ap.add_argument("--iter", type=int, default=3)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--rag-k", type=int, default=6, help="top-k chunks for RAG")
    ap.add_argument("--hier-ids", type=int, default=5, help="max doc ids from router")
    ap.add_argument("--reoptimize", action="store_true",
                    help="force re-run of the meta-harness optimizer")
    args = ap.parse_args()
    return asyncio.run(amain(args))


if __name__ == "__main__":
    sys.exit(main())
