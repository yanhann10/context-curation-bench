"""Analyze ConflictQA benchmark results.

Reads the experiment JSON and results CSV, produces summary statistics
including per-domain quality, stance bias analysis, and Pareto frontier.

Usage:
    python3 scripts/analyze_results.py output/conflictqa/experiment_YYYYMMDD_HHMMSS.json
"""
import json
import csv
import sys
from pathlib import Path
from collections import defaultdict


def load_experiment(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def load_results(csv_path: str) -> list[dict]:
    with open(csv_path) as f:
        return list(csv.DictReader(f))


def analyze(exp_path: str):
    exp = load_experiment(exp_path)
    csv_path = exp["artifacts"]["results_csv"]
    results = load_results(csv_path)

    print(f"{'='*72}")
    print(f"ConflictQA Benchmark Analysis")
    print(f"{'='*72}")
    print(f"Start: {exp['start_time']}")
    print(f"Duration: {exp['duration_human']}")
    print(f"Backend: {exp['backend']}")
    print(f"Agent: {exp['agent_model']}")
    print(f"Judge: {exp['judge_model']}")
    print(f"Cells: {exp['n_cells']} ({exp['n_strategies']} strategies × {exp['n_questions']} questions)")

    # Per-strategy summary
    print(f"\n{'strategy':<22} {'quality':>8} {'f1':>6} {'cost':>9}")
    print("-" * 50)
    for name, s in exp["summary"].items():
        print(f"{name:<22} {s['quality_mean']:>8.3f} {s['f1_mean']:>6.3f} {s['cost_usd_total']:>9.3f}")

    # Quality distribution
    print(f"\nQuality distribution by strategy:")
    by_strat = defaultdict(list)
    for r in results:
        by_strat[r["strategy"]].append(float(r["quality"]))

    for strat, quals in by_strat.items():
        bins = {"1.0": 0, "0.9": 0, "0.5-0.8": 0, "<0.5": 0}
        for q in quals:
            if q >= 0.95:
                bins["1.0"] += 1
            elif q >= 0.85:
                bins["0.9"] += 1
            elif q >= 0.5:
                bins["0.5-0.8"] += 1
            else:
                bins["<0.5"] += 1
        n = len(quals)
        print(f"  {strat:<22} ≥0.95:{bins['1.0']:3d}/{n}  0.85-0.94:{bins['0.9']:3d}/{n}  "
              f"0.5-0.84:{bins['0.5-0.8']:3d}/{n}  <0.5:{bins['<0.5']:3d}/{n}")

    # Frontier
    if "frontier" in exp:
        front = exp["frontier"]
        print(f"\nPareto frontier: {front['frontier']}")
        if front.get("dominated"):
            print(f"Dominated: {front['dominated']}")

    # Per-domain breakdown (if category metadata available)
    print(f"\nPer-domain quality (top 10 hardest):")
    by_question = defaultdict(lambda: defaultdict(float))
    for r in results:
        by_question[r["question_id"]][r["strategy"]] = float(r["quality"])

    q_avg = {}
    for qid, strats in by_question.items():
        q_avg[qid] = sum(strats.values()) / len(strats)

    hardest = sorted(q_avg.items(), key=lambda x: x[1])[:10]
    for qid, avg in hardest:
        strat_scores = by_question[qid]
        scores_str = " ".join(f"{s[:4]}={v:.2f}" for s, v in strat_scores.items())
        print(f"  {qid:16s} avg={avg:.3f}  {scores_str}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Find most recent experiment file
        exp_dir = Path("output/conflictqa")
        if exp_dir.exists():
            exps = sorted(exp_dir.glob("experiment_*.json"))
            if exps:
                analyze(str(exps[-1]))
            else:
                print("No experiment files found in output/conflictqa/")
        else:
            print("Usage: python3 scripts/analyze_results.py <experiment.json>")
    else:
        analyze(sys.argv[1])
