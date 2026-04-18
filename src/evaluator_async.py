"""Async answer + judge via Claude (Anthropic Messages API)."""
from __future__ import annotations
import asyncio
import json

from anthropic import AsyncAnthropic

from .evaluator import JUDGE_SYSTEM, RunResult
from .llm_client import complete_text, complete_json, cost_usd
from .metrics import f1 as _f1, exact_match as _em, key_facts_recall as _kfr


async def answer_question_async(
    client: AsyncAnthropic, prompt: str, model: str,
) -> tuple[str, float, int, int]:
    text, in_tok, out_tok, latency = await complete_text(
        client, user=prompt, system=None, model=model, max_tokens=1024,
    )
    return text, latency, in_tok, out_tok


async def judge_async(
    client: AsyncAnthropic, question: dict, answer: str, judge_model: str,
) -> tuple[float, int, str, int, int]:
    """Return (quality, recency, note, in_tok, out_tok)."""
    payload = {
        "question": question["question"],
        "category": question["category"],
        "golden_answer": question["golden_answer"],
        "key_facts": question["key_facts"],
        "agent_answer": answer,
    }
    data, in_tok, out_tok, _ = await complete_json(
        client,
        user=json.dumps(payload),
        system=JUDGE_SYSTEM,
        model=judge_model,
        max_tokens=256,
    )
    try:
        q = max(0.0, min(1.0, float(data.get("quality", 0.0))))
        r = 1 if int(data.get("recency", 0)) else 0
        note = str(data.get("note", ""))[:120]
        return q, r, note, in_tok, out_tok
    except Exception as e:
        return 0.0, 0, f"judge-parse-error: {e}", in_tok, out_tok


async def evaluate_one(
    client: AsyncAnthropic,
    strategy_name: str,
    prompt: str,
    question: dict,
    agent_model: str,
    judge_model: str,
) -> RunResult:
    try:
        ans, latency, in_tok, out_tok = await answer_question_async(client, prompt, agent_model)
        quality, recency, note, j_in, j_out = await judge_async(client, question, ans, judge_model)
        fail = ""
    except Exception as e:
        ans, latency, in_tok, out_tok = "", 0.0, 0, 0
        quality, recency, note, fail = 0.0, 0, "", f"error: {e}"
        j_in, j_out = 0, 0

    gold = question["golden_answer"]
    key_facts = question.get("key_facts", [])
    agent_cost = cost_usd(agent_model, in_tok, out_tok)
    judge_cost = cost_usd(judge_model, j_in, j_out)
    return RunResult(
        question_id=question["id"], strategy=strategy_name,
        question=question["question"], answer=ans,
        golden_answer=gold,
        quality=quality, recency=recency,
        f1=round(_f1(ans, gold), 3),
        exact_match=_em(ans, gold),
        key_fact_recall=round(_kfr(ans, key_facts), 3),
        latency_s=round(latency, 3),
        prompt_tokens=in_tok, completion_tokens=out_tok,
        total_tokens=in_tok + out_tok,
        cost_usd=round(agent_cost + judge_cost, 5),
        failure_note=fail or note,
    )


async def run_strategy_async(
    client: AsyncAnthropic,
    strategy_name: str,
    prompt_fn,
    questions: list[dict],
    docs: list[dict],
    agent_model: str,
    judge_model: str,
    concurrency: int = 8,
) -> list[RunResult]:
    sem = asyncio.Semaphore(concurrency)

    async def bounded(q):
        async with sem:
            prompt = prompt_fn(q["question"], docs)
            if asyncio.iscoroutine(prompt):
                prompt = await prompt
            return await evaluate_one(
                client, strategy_name, prompt, q, agent_model, judge_model,
            )

    return await asyncio.gather(*[bounded(q) for q in questions])
