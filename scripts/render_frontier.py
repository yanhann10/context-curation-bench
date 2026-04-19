"""Render a Pareto-frontier scatterplot from a ccbench summary.json.

Usage:
  python scripts/render_frontier.py output/summary_stage3.json assets/frontier_stage3.png
  python scripts/render_frontier.py <summary> <out> --oracle 1.000 0.138

Produces a cost-vs-quality scatter with the non-dominated set highlighted.
No LLM calls — just reads the committed summary numbers.

NOTE — the oracle marker is NOT derivable from summary.json (which only
holds per-strategy means). It is a meta-analysis over the per-question
matrix (cheapest max-quality pick per Q). Pass `--oracle Q C` to plot
one; omit to skip. Default matches the committed Stage-3 result
(1.000, $0.138).
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def is_dominated(name: str, summary: dict) -> bool:
    """Dominated if some other strategy is >= on quality AND <= on cost, strictly better on one."""
    q = summary[name]["quality_mean"]
    c = summary[name]["cost_usd_total"]
    for other, s in summary.items():
        if other == name:
            continue
        oq = s["quality_mean"]
        oc = s["cost_usd_total"]
        if oq >= q and oc <= c and (oq > q or oc < c):
            return True
    return False


def render(summary_path: str, out_path: str,
           oracle: tuple[float, float] | None = None) -> None:
    summary = load(summary_path)

    names = list(summary.keys())
    q = [summary[n]["quality_mean"] for n in names]
    c = [summary[n]["cost_usd_total"] for n in names]
    dominated = [is_dominated(n, summary) for n in names]

    fig, ax = plt.subplots(figsize=(8, 5.2), dpi=144)
    fig.patch.set_facecolor("#F4EFE6")
    ax.set_facecolor("#F4EFE6")

    for name, qi, ci, dom in zip(names, q, c, dominated):
        color = "#6E6557" if dom else "#C25B3F"
        size = 90 if dom else 220
        alpha = 0.55 if dom else 1.0
        ax.scatter(ci, qi, s=size, c=color, alpha=alpha, edgecolor="#141414", linewidth=1.2, zorder=3)
        dy = 0.006 if not dom else 0.004
        ax.annotate(
            name,
            xy=(ci, qi),
            xytext=(ci + 0.012, qi + dy),
            fontsize=9 if dom else 10,
            fontweight="bold" if not dom else "normal",
            color="#141414" if not dom else "#6E6557",
            zorder=4,
        )

    # oracle annotation (optional — not derivable from summary means)
    if oracle is not None:
        oracle_q, oracle_c = oracle
        ax.scatter([oracle_c], [oracle_q], s=260, marker="*", c="#D4A11A",
                   edgecolor="#141414", linewidth=1.2, zorder=5)
        ax.annotate("oracle router\n(theoretical)", xy=(oracle_c, oracle_q),
                    xytext=(oracle_c + 0.03, oracle_q - 0.005),
                    fontsize=9, fontweight="bold", color="#141414", zorder=5)

    ax.set_xlabel("cost per 10 questions (USD)", fontsize=11)
    ax.set_ylabel("quality (LLM-judge, 0–1)", fontsize=11)
    ax.set_title("ccbench Stage 3 — Pareto frontier (7 strategies, N=10)",
                 fontsize=12, fontweight="bold", pad=12)
    ax.grid(True, alpha=0.25, linestyle="--", zorder=1)
    ax.set_xlim(0, max(c) * 1.15)
    ax.set_ylim(min(q) - 0.02, 1.015)

    # legend
    ax.scatter([], [], s=220, c="#C25B3F", edgecolor="#141414",
               linewidth=1.2, label="Pareto non-dominated")
    ax.scatter([], [], s=90, c="#6E6557", edgecolor="#141414",
               linewidth=1.2, alpha=0.55, label="dominated")
    if oracle is not None:
        ax.scatter([], [], s=260, marker="*", c="#D4A11A",
                   edgecolor="#141414", linewidth=1.2, label="oracle (per-Q pick)")
    ax.legend(loc="lower right", framealpha=0.9, facecolor="#EBE3D3")

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"wrote {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("summary", nargs="?", default="output/summary_stage3.json")
    ap.add_argument("out", nargs="?", default="assets/frontier_stage3.png")
    ap.add_argument("--oracle", nargs=2, type=float, metavar=("QUALITY", "COST"),
                    default=[1.000, 0.138],
                    help="oracle router point (quality, cost). Pass '--oracle 0 0' or "
                         "'--no-oracle' to omit.")
    ap.add_argument("--no-oracle", action="store_true", help="skip the oracle marker")
    args = ap.parse_args()
    oracle = None if args.no_oracle else tuple(args.oracle)
    render(args.summary, args.out, oracle=oracle)
