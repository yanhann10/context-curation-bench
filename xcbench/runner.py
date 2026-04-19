"""Strategy × Question matrix runner. Async throughout.

Flow per cell:
  1. call strategy(ctx, question, corpus, **params)
     - if it returns str   -> runner issues an agent call with that prompt
     - if it returns dict  -> runner uses the pre-computed answer + tokens
  2. call grader(ctx, question, answer)
  3. compute f1 / EM / key-fact recall / cost from metrics.py
  4. emit a CellResult dict
"""
from __future__ import annotations
import asyncio
import inspect
from dataclasses import dataclass, asdict

from .registry import STRATEGIES, GRADERS
from src.llm_client import complete_text, cost_usd
from src.metrics import f1 as _f1, exact_match as _em, key_facts_recall as _kfr


@dataclass
class CellResult:
    question_id: str
    strategy: str
    category: str
    question: str
    answer: str
    golden: str
    quality: float
    f1: float
    exact_match: float
    key_fact_recall: float
    latency_s: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    note: str


async def _run_one(ctx, strategy_cfg, question, corpus) -> CellResult:
    fn = STRATEGIES[strategy_cfg.name]
    try:
        out = await fn(ctx, question, corpus, **(strategy_cfg.params or {}))
        if isinstance(out, str):
            text, in_tok, out_tok, latency = await complete_text(
                ctx["client"], user=out, system=None,
                model=ctx["agent_model"], max_tokens=1024,
            )
            answer = text
        elif isinstance(out, dict):
            answer = out["answer"]
            in_tok = out["prompt_tokens"]
            out_tok = out["completion_tokens"]
            latency = out["latency_s"]
        else:
            raise TypeError(f"strategy {strategy_cfg.name} returned {type(out).__name__}")
        fail = ""
    except Exception as e:
        answer, in_tok, out_tok, latency = "", 0, 0, 0.0
        fail = f"strategy-error: {e}"

    grader_fn = GRADERS[ctx["grader_name"]]
    try:
        g = await grader_fn(ctx, question, answer) if answer else {"quality": 0.0, "note": fail}
    except Exception as e:
        g = {"quality": 0.0, "note": f"grader-error: {e}"}

    j_in = g.get("judge_prompt_tokens", 0)
    j_out = g.get("judge_completion_tokens", 0)
    agent_cost = cost_usd(ctx["agent_model"], in_tok, out_tok)
    judge_cost = cost_usd(ctx.get("judge_model", ""), j_in, j_out)

    return CellResult(
        question_id=question.id,
        strategy=strategy_cfg.name,
        category=question.category,
        question=question.input,
        answer=answer,
        golden=question.golden,
        quality=float(g.get("quality", 0.0)),
        f1=round(_f1(answer, question.golden), 3),
        exact_match=_em(answer, question.golden),
        key_fact_recall=round(_kfr(answer, question.key_facts), 3),
        latency_s=round(latency, 3),
        prompt_tokens=in_tok,
        completion_tokens=out_tok,
        total_tokens=in_tok + out_tok,
        cost_usd=round(agent_cost + judge_cost, 5),
        note=(fail or g.get("note", ""))[:200],
    )


async def run_matrix(ctx, strategies, questions, corpus, concurrency: int = 8) -> list[CellResult]:
    sem = asyncio.Semaphore(concurrency)

    async def bounded(s, q):
        async with sem:
            return await _run_one(ctx, s, q, corpus)

    tasks = [bounded(s, q) for s in strategies for q in questions]
    return await asyncio.gather(*tasks)


def results_by_strategy(results: list[CellResult]) -> dict[str, list[CellResult]]:
    out: dict[str, list[CellResult]] = {}
    for r in results:
        out.setdefault(r.strategy, []).append(r)
    return out


def summarize(results: list[CellResult]) -> dict:
    by_s = results_by_strategy(results)
    summary = {}
    for name, rs in by_s.items():
        n = max(len(rs), 1)
        by_cat: dict[str, list[float]] = {}
        for r in rs:
            by_cat.setdefault(r.category or "uncategorized", []).append(r.quality)
        summary[name] = {
            "n": n,
            "quality_mean": round(sum(r.quality for r in rs) / n, 3),
            "f1_mean": round(sum(r.f1 for r in rs) / n, 3),
            "em_mean": round(sum(r.exact_match for r in rs) / n, 3),
            "key_fact_recall_mean": round(sum(r.key_fact_recall for r in rs) / n, 3),
            "latency_s_mean": round(sum(r.latency_s for r in rs) / n, 3),
            "prompt_tokens_mean": round(sum(r.prompt_tokens for r in rs) / n),
            "total_tokens_mean": round(sum(r.total_tokens for r in rs) / n),
            "cost_usd_total": round(sum(r.cost_usd for r in rs), 5),
            "quality_by_category": {
                c: round(sum(v) / len(v), 3) for c, v in by_cat.items()
            },
        }
    return summary
