"""ccbench CLI.

  python -m ccbench run suites/hr_living_docs.yaml [--output output/matrix.csv]
  python -m ccbench validate suites/hr_living_docs.yaml
  python -m ccbench list-strategies
  python -m ccbench list-graders
"""
from __future__ import annotations
import argparse
import asyncio
import csv
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from dotenv import load_dotenv
from anthropic import AsyncAnthropic

from . import (  # noqa: F401  register built-ins
    judge, strategies,
)
from .registry import STRATEGIES, GRADERS, CORPUS_LOADERS
from .spec import load_suite, validate
from .dataset import load_questions
from .runner import run_matrix, summarize, CellResult
from . import frontier, optimizer


def cmd_list(kind: str) -> int:
    table = {"strategies": STRATEGIES, "graders": GRADERS, "corpus-loaders": CORPUS_LOADERS}
    reg = table[kind]
    for n in sorted(reg):
        print(f"  {n}")
    return 0


def cmd_validate(suite_path: str) -> int:
    spec = load_suite(suite_path)
    errs = validate(spec)
    if errs:
        print("INVALID")
        for e in errs:
            print(f"  - {e}")
        return 1
    print(f"OK — suite '{spec.name}' with {len(spec.strategies)} strategies")
    return 0


async def _run(suite_path: str, output_path: str) -> int:
    spec = load_suite(suite_path)
    errs = validate(spec)
    if errs:
        print("suite invalid:")
        for e in errs:
            print(f"  - {e}")
        return 1

    load_dotenv(Path(".env"))
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 2

    client = AsyncAnthropic(api_key=key)
    loader = CORPUS_LOADERS[spec.corpus.loader]
    corpus = loader(spec.corpus.path)
    questions = load_questions(spec.dataset.path)
    print(f"suite={spec.name}  corpus={len(corpus.docs)} docs  "
          f"questions={len(questions)}  strategies={[s.name for s in spec.strategies]}")

    ctx = {
        "client": client,
        "agent_model": spec.models.agent,
        "judge_model": spec.models.judge,
        "proposer_model": spec.models.proposer,
        "concurrency": spec.concurrency,
        "grader_name": spec.grader.kind,
    }

    history = None
    if spec.optimize:
        train = questions[: spec.optimize.train_size]
        print(f"\n[optimize] fitting '{spec.optimize.strategy}' on "
              f"{len(train)} questions, {spec.optimize.iterations} iterations")
        fitted, history = await optimizer.fit(
            ctx, spec.optimize.strategy, train, corpus,
            iterations=spec.optimize.iterations,
        )
        ctx["fitted_spec"] = fitted
        print(f"[optimize] final spec: {fitted.describe()}")

    print(f"\n[matrix] running {len(spec.strategies)} × {len(questions)} cells")
    results = await run_matrix(ctx, spec.strategies, questions, corpus, spec.concurrency)

    out_dir = Path(output_path).parent if output_path else Path("output")
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = Path(output_path) if output_path else out_dir / f"{spec.name}_matrix.csv"
    fieldnames = list(asdict(results[0]).keys())
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in results:
            row = asdict(r)
            for k in ("answer", "golden", "question"):
                row[k] = row[k].replace("\n", " ")[:500]
            w.writerow(row)

    summary = summarize(results)
    summary_path = out_dir / f"{spec.name}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    front = frontier.compute(summary, spec.frontier.axes, spec.frontier.direction)
    front_path = out_dir / f"{spec.name}_frontier.json"
    front_path.write_text(json.dumps(front, indent=2), encoding="utf-8")

    if history is not None:
        (out_dir / f"{spec.name}_optimizer_history.json").write_text(
            json.dumps(history, indent=2, default=str), encoding="utf-8",
        )

    print("\n" + "=" * 72)
    print(f"SUITE SUMMARY — {spec.name}")
    print("=" * 72)
    hdr = f"{'strategy':<22} {'quality':>8} {'f1':>6} {'tokens':>8} {'cost_usd':>9} {'latency':>8}"
    print(hdr)
    for name, s in summary.items():
        print(f"{name:<22} {s['quality_mean']:>8.3f} {s['f1_mean']:>6.3f} "
              f"{s['total_tokens_mean']:>8d} {s['cost_usd_total']:>9.3f} "
              f"{s['latency_s_mean']:>8.2f}")
    print("\n" + frontier.render(front, spec.frontier.axes))
    print(f"\nArtifacts:\n  {csv_path}\n  {summary_path}\n  {front_path}")
    return 0


def cmd_run(suite_path: str, output: str) -> int:
    return asyncio.run(_run(suite_path, output))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ccbench")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run")
    r.add_argument("suite")
    r.add_argument("--output", default="")

    v = sub.add_parser("validate")
    v.add_argument("suite")

    sub.add_parser("list-strategies")
    sub.add_parser("list-graders")
    sub.add_parser("list-corpus-loaders")

    args = ap.parse_args(argv)
    if args.cmd == "run":
        return cmd_run(args.suite, args.output)
    if args.cmd == "validate":
        return cmd_validate(args.suite)
    if args.cmd == "list-strategies":
        return cmd_list("strategies")
    if args.cmd == "list-graders":
        return cmd_list("graders")
    if args.cmd == "list-corpus-loaders":
        return cmd_list("corpus-loaders")
    return 2


if __name__ == "__main__":
    sys.exit(main())
