"""Async variants of answer + judge. Compatible with evaluator.RunResult."""
from __future__ import annotations
import asyncio
import json
import os
import time

from openai import AsyncOpenAI

from .evaluator import JUDGE_SYSTEM, cost_usd, RunResult


async def answer_question_async(
    client: AsyncOpenAI, prompt: str, model: str,
) -> tuple[str, float, int, int]:
    t0 = time.time()
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )
    latency = time.time() - t0
    answer = resp.choices[0].message.content or ""
    u = resp.usage
    return answer, latency, u.prompt_tokens, u.completion_tokens


async def judge_async(
    client: AsyncOpenAI, question: dict, answer: str, judge_model: str,
) -> tuple[float, int, str]:
    payload = {
        "question": question["question"],
        "category": question["category"],
        "golden_answer": question["golden_answer"],
        "key_facts": question["key_facts"],
        "agent_answer": answer,
    }
    resp = await client.chat.completions.create(
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
        q = max(0.0, min(1.0, float(data.get("quality", 0.0))))
        r = 1 if int(data.get("recency", 0)) else 0
        note = str(data.get("note", ""))[:120]
        return q, r, note
    except Exception as e:
        return 0.0, 0, f"judge-parse-error: {e}"


async def evaluate_one(
    client: AsyncOpenAI,
    strategy_name: str,
    prompt: str,
    question: dict,
    agent_model: str,
    judge_model: str,
) -> RunResult:
    try:
        ans, latency, in_tok, out_tok = await answer_question_async(client, prompt, agent_model)
        quality, recency, note = await judge_async(client, question, ans, judge_model)
        fail = ""
    except Exception as e:
        ans, latency, in_tok, out_tok, quality, recency, note, fail = (
            "", 0.0, 0, 0, 0.0, 0, "", f"error: {e}"
        )
    return RunResult(
        question_id=question["id"], strategy=strategy_name,
        question=question["question"], answer=ans,
        golden_answer=question["golden_answer"],
        quality=quality, recency=recency, latency_s=round(latency, 3),
        prompt_tokens=in_tok, completion_tokens=out_tok,
        total_tokens=in_tok + out_tok,
        cost_usd=round(cost_usd(in_tok, out_tok), 5),
        failure_note=fail or note,
    )


async def run_strategy_async(
    client: AsyncOpenAI,
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
