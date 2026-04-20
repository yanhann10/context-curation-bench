"""Run ConflictQA benchmark: 6 strategies × 120 questions.

Tracks datetime, duration, and per-category metrics.
Saves results incrementally and produces a final experiment log.

Usage:
    python3 scripts/run_conflictqa_bench.py [--concurrency 4] [--strategies full_context,rag_embedding]
"""
import argparse
import asyncio
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is importable
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")


async def main(args):
    start_time = datetime.now(timezone.utc)
    print(f"[{start_time.isoformat()}] ConflictQA Benchmark — starting")
    print(f"  Strategies: {args.strategies}")
    print(f"  Concurrency: {args.concurrency}")

    # Import after path setup
    from xcbench.spec import load_suite
    from xcbench.backend import make_client, resolve_model
    from xcbench.corpus import load_jsonl
    from xcbench.dataset import load_questions
    from xcbench.runner import run_matrix, summarize, CellResult
    from xcbench.frontier import compute, render
    from xcbench.registry import STRATEGIES, GRADERS

    # Register built-ins
    import xcbench.strategies  # noqa
    import xcbench.judge  # noqa

    spec = load_suite("suites/conflictqa.yaml")
    client, backend = make_client()

    corpus = load_jsonl(spec.corpus.path)
    questions = load_questions(spec.dataset.path)
    print(f"  Corpus: {len(corpus.docs)} docs")
    print(f"  Questions: {len(questions)}")

    agent_model = resolve_model(spec.models.agent, backend)
    judge_model = resolve_model(spec.models.judge, backend)
    print(f"  Agent: {agent_model}")
    print(f"  Judge: {judge_model}")

    if agent_model == judge_model:
        print("  ⚠️  Agent == Judge — self-preference bias likely")

    ctx = {
        "client": client,
        "agent_model": agent_model,
        "judge_model": judge_model,
        "concurrency": args.concurrency,
        "grader_name": "llm_judge",
    }

    # Filter strategies if specified
    strategy_cfgs = [s for s in spec.strategies if s.name in args.strategies]
    if not strategy_cfgs:
        print(f"ERROR: no matching strategies. Available: {[s.name for s in spec.strategies]}")
        return

    print(f"\n[matrix] Running {len(strategy_cfgs)} × {len(questions)} = {len(strategy_cfgs)*len(questions)} cells")

    matrix_start = time.time()
    results = await run_matrix(ctx, strategy_cfgs, questions, corpus, args.concurrency)
    matrix_duration = time.time() - matrix_start

    # Save results
    out_dir = Path("output/conflictqa")
    out_dir.mkdir(parents=True, exist_ok=True)

    ts_slug = start_time.strftime("%Y%m%d_%H%M%S")

    # CSV
    csv_path = out_dir / f"results_{ts_slug}.csv"
    from dataclasses import asdict
    fieldnames = list(asdict(results[0]).keys())
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in results:
            row = asdict(r)
            for k in ("answer", "golden", "question"):
                row[k] = row[k].replace("\n", " ")[:500]
            w.writerow(row)

    # Summary
    summary = summarize(results)
    summary_path = out_dir / f"summary_{ts_slug}.json"
    summary_path.write_text(json.dumps(summary, indent=2))

    # Frontier
    front = compute(summary, ["quality", "cost_usd", "total_tokens"], ["max", "min", "min"])

    end_time = datetime.now(timezone.utc)
    total_duration = (end_time - start_time).total_seconds()

    # Print results
    print(f"\n{'='*72}")
    print(f"CONFLICTQA BENCHMARK — {len(questions)} questions × {len(strategy_cfgs)} strategies")
    print(f"{'='*72}")
    hdr = f"{'strategy':<22} {'quality':>8} {'f1':>6} {'tokens':>8} {'cost_usd':>9} {'latency':>8}"
    print(hdr)
    for name, s in summary.items():
        print(f"{name:<22} {s['quality_mean']:>8.3f} {s['f1_mean']:>6.3f} "
              f"{s['total_tokens_mean']:>8d} {s['cost_usd_total']:>9.3f} "
              f"{s['latency_s_mean']:>8.2f}")

    print(f"\n{render(front, ['quality', 'cost_usd', 'total_tokens'])}")

    # Experiment log
    experiment_log = {
        "experiment": "conflictqa_bench",
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_s": round(total_duration, 1),
        "duration_human": f"{total_duration/60:.1f}min",
        "matrix_duration_s": round(matrix_duration, 1),
        "backend": backend,
        "agent_model": agent_model,
        "judge_model": judge_model,
        "strategies": [s.name for s in strategy_cfgs],
        "n_questions": len(questions),
        "n_strategies": len(strategy_cfgs),
        "n_cells": len(results),
        "concurrency": args.concurrency,
        "summary": summary,
        "frontier": front,
        "artifacts": {
            "results_csv": str(csv_path),
            "summary_json": str(summary_path),
        },
    }
    log_path = out_dir / f"experiment_{ts_slug}.json"
    log_path.write_text(json.dumps(experiment_log, indent=2))

    print(f"\nDuration: {total_duration:.0f}s ({total_duration/60:.1f}min)")
    print(f"Artifacts: {csv_path}, {summary_path}, {log_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--strategies", type=str,
                        default="full_context,rag_embedding,hierarchical,agent_managed,cascade,ensemble")
    args = parser.parse_args()
    args.strategies = [s.strip() for s in args.strategies.split(",")]
    asyncio.run(main(args))
