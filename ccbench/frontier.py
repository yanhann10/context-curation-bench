"""Pareto-frontier gate.

Instead of a boolean pass/fail like letta-evals `gate:`, we compute the set
of non-dominated strategies over a list of axes. A strategy is *dominated*
if some other strategy is at least as good on every axis and strictly
better on one.

Inputs:
  summary  : {strategy_name: {axis_name: float, ...}}
  axes     : ["quality", "cost_usd", "total_tokens"]
  direction: ["max", "min", "min"]

Returns a dict:
  {
    "frontier":       [strategy names that are non-dominated],
    "dominated":      {name: [dominators]},
    "per_axis_best":  {axis: strategy_name},
  }
"""
from __future__ import annotations


def _better(a: float, b: float, direction: str) -> bool:
    return a > b if direction == "max" else a < b


def _ge(a: float, b: float, direction: str) -> bool:
    return a >= b if direction == "max" else a <= b


def compute(
    summary: dict[str, dict],
    axes: list[str],
    direction: list[str],
    axis_aliases: dict[str, str] | None = None,
) -> dict:
    aliases = axis_aliases or {
        "quality": "quality_mean",
        "cost_usd": "cost_usd_total",
        "total_tokens": "total_tokens_mean",
        "tokens": "total_tokens_mean",
        "latency": "latency_s_mean",
        "f1": "f1_mean",
    }
    resolved = [aliases.get(a, a) for a in axes]

    names = list(summary.keys())
    values = {n: [summary[n].get(ax, 0.0) for ax in resolved] for n in names}

    dominated: dict[str, list[str]] = {}
    for n in names:
        doms = []
        for m in names:
            if m == n:
                continue
            strictly_better_one = False
            worse_on_any = False
            for i, dirn in enumerate(direction):
                if _better(values[m][i], values[n][i], dirn):
                    strictly_better_one = True
                elif not _ge(values[m][i], values[n][i], dirn):
                    worse_on_any = True
                    break
            if strictly_better_one and not worse_on_any:
                doms.append(m)
        if doms:
            dominated[n] = doms

    frontier = [n for n in names if n not in dominated]

    per_axis_best = {}
    for i, (ax, dirn) in enumerate(zip(axes, direction)):
        winner = None
        best = None
        for n in names:
            v = values[n][i]
            if best is None or _better(v, best, dirn):
                best = v
                winner = n
        per_axis_best[ax] = winner

    return {
        "frontier": frontier,
        "dominated": dominated,
        "per_axis_best": per_axis_best,
    }


def render(report: dict, axes: list[str]) -> str:
    lines = []
    lines.append(f"Pareto frontier over {axes}:")
    for n in report["frontier"]:
        lines.append(f"  * {n}   <-- non-dominated")
    for n, doms in report["dominated"].items():
        lines.append(f"  . {n}   dominated by: {', '.join(doms)}")
    lines.append("")
    lines.append("Per-axis winners:")
    for ax, win in report["per_axis_best"].items():
        lines.append(f"  {ax:>16s}: {win}")
    return "\n".join(lines)
