"""LLM-as-judge scoring + per-run metrics logging (Claude backend)."""
from __future__ import annotations
import csv
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class RunResult:
    question_id: str
    strategy: str
    question: str
    answer: str
    golden_answer: str
    quality: float
    f1: float
    exact_match: float
    key_fact_recall: float
    latency_s: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    failure_note: str


JUDGE_SYSTEM = (
    "You are a strict evaluator grading a New Hire Onboarding Agent's answer "
    "against a golden answer. Output VALID JSON only with exact keys: "
    '{"quality": <float 0..1>, "note": "<short reason, <=120 chars>"}. '
    "quality = correctness vs golden_answer (1 = fully correct, 0.5 = partially correct, 0 = wrong/missing). "
    "For recency-sensitive questions (category == 'slack_contradicts' or key_facts mention a recent update), "
    "an answer that uses the stale handbook value instead of the recent Slack value should score <= 0.5."
)


def log_results(results: list[RunResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(results[0]).keys()) if results else []
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in results:
            row = asdict(r)
            row["answer"] = row["answer"].replace("\n", " ")[:500]
            row["golden_answer"] = row["golden_answer"].replace("\n", " ")[:300]
            row["question"] = row["question"].replace("\n", " ")[:200]
            w.writerow(row)


def summarize(results: list[RunResult]) -> dict:
    by_strat: dict[str, list[RunResult]] = {}
    for r in results:
        by_strat.setdefault(r.strategy, []).append(r)
    summary = {}
    for strat, rs in by_strat.items():
        n = len(rs)
        summary[strat] = {
            "n": n,
            "quality_mean": round(sum(r.quality for r in rs) / n, 3),
            "f1_mean": round(sum(r.f1 for r in rs) / n, 3),
            "exact_match_mean": round(sum(r.exact_match for r in rs) / n, 3),
            "key_fact_recall_mean": round(sum(r.key_fact_recall for r in rs) / n, 3),
            "latency_s_mean": round(sum(r.latency_s for r in rs) / n, 3),
            "prompt_tokens_mean": round(sum(r.prompt_tokens for r in rs) / n),
            "completion_tokens_mean": round(sum(r.completion_tokens for r in rs) / n),
            "cost_usd_total": round(sum(r.cost_usd for r in rs), 5),
        }
    return summary
