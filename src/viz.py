"""Quick demo-day charts — quality vs cost/tokens + per-question heatmap.

No interactive output; saves PNGs. Run:
    python -m src.viz output/results_stage2.csv output/chart_stage2.png
"""
from __future__ import annotations
import csv
import sys
from collections import defaultdict
from pathlib import Path


def _load_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def plot_quality_vs_cost(csv_path: Path, out_path: Path) -> None:
    import matplotlib.pyplot as plt
    rows = _load_csv(csv_path)
    by_strat: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_strat[r["strategy"]].append(r)

    strats = list(by_strat.keys())
    q_mean = [sum(float(r["quality"]) for r in by_strat[s]) / len(by_strat[s]) for s in strats]
    cost_total = [sum(float(r["cost_usd"]) for r in by_strat[s]) for s in strats]
    tok_mean = [sum(int(r["prompt_tokens"]) for r in by_strat[s]) / len(by_strat[s]) for s in strats]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # Left: quality bar + cost overlay
    x = range(len(strats))
    bars = ax1.bar(x, q_mean, color=["#4C72B0", "#55A868", "#C44E52", "#8172B2"][:len(strats)])
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(strats, rotation=15, ha="right")
    ax1.set_ylim(0, 1.05)
    ax1.set_ylabel("Quality (LLM-judge, 0-1)")
    ax1.set_title("Quality by strategy")
    for bar, v in zip(bars, q_mean):
        ax1.text(bar.get_x() + bar.get_width() / 2, v + 0.01, f"{v:.2f}", ha="center", fontsize=10)

    # Right: cost vs prompt-tokens (log scale on tokens)
    ax2.scatter(tok_mean, cost_total, s=180, c=["#4C72B0", "#55A868", "#C44E52", "#8172B2"][:len(strats)])
    for s, x_v, y_v in zip(strats, tok_mean, cost_total):
        ax2.annotate(s, (x_v, y_v), xytext=(8, 6), textcoords="offset points", fontsize=9)
    ax2.set_xscale("log")
    ax2.set_xlabel("Avg prompt tokens per question (log)")
    ax2.set_ylabel("Total cost USD across question set")
    ax2.set_title("Cost vs context size")
    ax2.grid(True, which="both", ls=":", alpha=0.4)

    fig.suptitle(f"Context curation strategies — {csv_path.name}", fontsize=13)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out_path}")


def plot_heatmap(csv_path: Path, out_path: Path) -> None:
    """Per-question × strategy quality grid."""
    import matplotlib.pyplot as plt
    import numpy as np
    rows = _load_csv(csv_path)
    strats = sorted({r["strategy"] for r in rows})
    qids = sorted({r["question_id"] for r in rows})
    mat = np.zeros((len(qids), len(strats)), dtype=float)
    for r in rows:
        i = qids.index(r["question_id"])
        j = strats.index(r["strategy"])
        mat[i, j] = float(r["quality"])

    fig, ax = plt.subplots(figsize=(max(6, 1.2 * len(strats) + 3), 0.55 * len(qids) + 1.5))
    im = ax.imshow(mat, vmin=0, vmax=1, cmap="RdYlGn", aspect="auto")
    ax.set_xticks(range(len(strats)))
    ax.set_xticklabels(strats, rotation=20, ha="right")
    ax.set_yticks(range(len(qids)))
    ax.set_yticklabels(qids)
    for i in range(len(qids)):
        for j in range(len(strats)):
            ax.text(j, i, f"{mat[i,j]:.2f}", ha="center", va="center", color="black", fontsize=9)
    fig.colorbar(im, ax=ax, shrink=0.7, label="Quality (LLM-judge)")
    ax.set_title(f"Per-question quality — {csv_path.name}")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out_path}")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -m src.viz <results.csv> [out.png]", file=sys.stderr)
        return 2
    csv_path = Path(sys.argv[1])
    out_base = Path(sys.argv[2]) if len(sys.argv) > 2 else csv_path.with_suffix(".png")
    plot_quality_vs_cost(csv_path, out_base)
    plot_heatmap(csv_path, out_base.with_name(out_base.stem + "_heatmap.png"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
