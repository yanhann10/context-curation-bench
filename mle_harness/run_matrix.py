"""Matrix runner: competitions × harnesses.

  python -m mle_harness.run_matrix --comps spooky-author-identification --harnesses full_context,agent_managed
"""
from __future__ import annotations
import argparse
import asyncio
import csv
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

from mle_harness.executor import run_cell, CellResult
from mle_harness.harnesses import HARNESSES


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--comps", required=True, help="comma-separated competition ids")
    ap.add_argument("--harnesses", default="full_context,agent_managed")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--out", default="output/mle_matrix.csv")
    args = ap.parse_args()

    comps = [c.strip() for c in args.comps.split(",") if c.strip()]
    harnesses = [h.strip() for h in args.harnesses.split(",") if h.strip()]
    for h in harnesses:
        if h not in HARNESSES:
            print(f"ERROR: unknown harness '{h}'. Available: {list(HARNESSES)}")
            return 2

    print(f"Running {len(comps)} comp × {len(harnesses)} harness = {len(comps) * len(harnesses)} cells")
    results: list[CellResult] = []
    for c in comps:
        for h in harnesses:
            print(f"\n[cell] comp={c}  harness={h}")
            t0 = time.time()
            r = run_cell(c, h, HARNESSES[h], timeout_s=args.timeout)
            results.append(r)
            print(f"   submitted={r.submitted}  score={r.score}  medal={r.medal}  "
                  f"cost=${r.cost_usd:.3f}  wall={r.wall_time_s:.1f}s  "
                  f"err={(r.error or '')[:80]}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = list(asdict(results[0]).keys()) if results else []
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in results:
            row = asdict(r)
            row["error"] = (row.get("error") or "").replace("\n", " ")[:300]
            w.writerow(row)

    print(f"\n=== SUMMARY ===")
    print(f"{'comp':<40} {'harness':<18} {'sub?':>4} {'score':>8} {'medal':>7} {'cost':>8}")
    for r in results:
        print(f"{r.competition:<40} {r.harness:<18} "
              f"{'Y' if r.submitted else '-':>4} "
              f"{r.score if r.score is not None else '-':>8} "
              f"{r.medal or '-':>7} "
              f"${r.cost_usd:>7.3f}")
    print(f"\nArtifacts: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
