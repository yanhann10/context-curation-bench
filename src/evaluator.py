"""LLM-as-judge scoring + per-run metrics logging.

Metrics per (question, strategy) run:
  quality  float in [0,1]
  recency  0|1 (did the answer use the recent Slack fact when one exists?)
  latency  seconds
  prompt_tokens / completion_tokens / total_tokens
  cost_usd (approximate, gpt-4o-mini priced)
  failure_note  short string or ""
"""
from __future__ import annotations
import csv
import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path

from openai import OpenAI


# gpt-4o-mini pricing (per 1M tokens) as of 2026-04.
# Override via env if needed.
PRICE_IN = float(os.getenv("AGENT_PRICE_IN_PER_M", "0.150"))
PRICE_OUT = float(os.getenv("AGENT_PRICE_OUT_PER_M", "0.600"))


@dataclass
class RunResult:
    question_id: str
    strategy: str
    question: str
    answer: str
    golden_answer: str
    quality: float
    recency: int
    latency_s: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    failure_note: str


def answer_question(
    client: OpenAI,
    prompt: str,
    model: str,
) -> tuple[str, float, int, int]:
    """Run the agent and return (answer, latency_s, in_tok, out_tok)."""
    t0 = time.time()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )
    latency = time.time() - t0
    answer = resp.choices[0].message.content or ""
    u = resp.usage
    return answer, latency, u.prompt_tokens, u.completion_tokens


JUDGE_SYSTEM = (
    "You are a strict evaluator grading a New Hire Onboarding Agent's answer "
    "against a golden answer. Output VALID JSON only with exact keys: "
    '{"quality": <float 0..1>, "recency": <0|1>, "note": "<short reason, <=120 chars>"}. '
    "quality = correctness vs golden_answer (1 = fully correct, 0.5 = partially correct, 0 = wrong/missing). "
    "recency = 1 if the answer reflects the most recent fact when the question has a recency-sensitive golden "
    "(i.e. 'slack_contradicts' or key_facts mention a recent update); else 0. "
    "If the question is NOT recency-sensitive (category == 'portal_only' or 'slack_only'), set recency = 1 when "
    "correct and 0 when wrong — i.e., treat it as a second copy of quality rounded."
)


def judge(
    client: OpenAI,
    question: dict,
    answer: str,
    judge_model: str,
) -> tuple[float, int, str]:
    """Return (quality, recency, note)."""
    payload = {
        "question": question["question"],
        "category": question["category"],
        "golden_answer": question["golden_answer"],
        "key_facts": question["key_facts"],
        "agent_answer": answer,
    }
    resp = client.chat.completions.create(
        model=judge_model,
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": json.dumps(payload)},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
        q = float(data.get("quality", 0.0))
        r = int(data.get("recency", 0))
        note = str(data.get("note", ""))[:120]
        q = max(0.0, min(1.0, q))
        r = 1 if r else 0
        return q, r, note
    except Exception as e:
        return 0.0, 0, f"judge-parse-error: {e}"


def cost_usd(in_tok: int, out_tok: int) -> float:
    return in_tok * PRICE_IN / 1_000_000 + out_tok * PRICE_OUT / 1_000_000


def log_results(results: list[RunResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(results[0]).keys()) if results else []
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in results:
            row = asdict(r)
            # Keep CSV compact — trim long fields.
            row["answer"] = row["answer"].replace("\n", " ")[:500]
            row["golden_answer"] = row["golden_answer"].replace("\n", " ")[:300]
            row["question"] = row["question"].replace("\n", " ")[:200]
            w.writerow(row)


def summarize(results: list[RunResult]) -> dict:
    """Aggregate per-strategy means."""
    by_strat: dict[str, list[RunResult]] = {}
    for r in results:
        by_strat.setdefault(r.strategy, []).append(r)
    summary = {}
    for strat, rs in by_strat.items():
        n = len(rs)
        summary[strat] = {
            "n": n,
            "quality_mean": round(sum(r.quality for r in rs) / n, 3),
            "recency_mean": round(sum(r.recency for r in rs) / n, 3),
            "latency_s_mean": round(sum(r.latency_s for r in rs) / n, 3),
            "prompt_tokens_mean": round(sum(r.prompt_tokens for r in rs) / n),
            "completion_tokens_mean": round(sum(r.completion_tokens for r in rs) / n),
            "cost_usd_total": round(sum(r.cost_usd for r in rs), 5),
        }
    return summary
