"""Ensemble routing: run two strategies in parallel, LLM-judge picks the better answer.

Default pair: hierarchical (~91.5% quality, cheap) + agent_managed (~99.5% quality, mid).
Judge is asked to return A or B based on correctness + specificity.

Cost = tokens(hier) + tokens(agent) + tokens(judge-pick). Always pays both —
the upside over cascade is latency (parallel) and better coverage when one
strategy's failure is silent (no low confidence signal).
"""
from __future__ import annotations
import asyncio
import time

from anthropic import AsyncAnthropic

from .llm_client import complete_json
from .evaluator_async import answer_question_async
from .strategies_agent_managed import agent_managed_runner


PICK_SYSTEM = (
    "You are selecting the better answer to a user question. You will see "
    "Answer A and Answer B. Pick the one that is more correct and more "
    "specific. If both are correct, prefer the one that cites source titles. "
    'Return JSON only: {"pick": "A"|"B", "reason": "<short, <=80 chars>"}'
)


def make_ensemble_runner(hier_prompt_fn, judge_model: str | None = None):
    """Factory returning a runner that runs hier + agent_managed in parallel.

    judge_model: if set, use this model for the A-vs-B picker instead of the
    answerer model. Use a cheaper model (e.g. claude-haiku-4-5) to reduce
    ensemble cost by ~20% with minimal quality risk.
    """
    async def ensemble_runner(
        client: AsyncAnthropic, question: str, docs: list[dict], model: str,
    ) -> tuple[str, float, int, int]:
        t0 = time.time()
        j_model = judge_model or model

        async def run_hier():
            prompt = await hier_prompt_fn(question, docs)
            return await answer_question_async(client, prompt, model)

        (ans_a, _, a_in, a_out), (ans_b, _, b_in, b_out) = await asyncio.gather(
            run_hier(),
            agent_managed_runner(client, question, docs, model),
        )

        payload = (
            f"Question: {question}\n\n"
            f"Answer A (hierarchical):\n{ans_a[:1500]}\n\n"
            f"Answer B (agent_managed):\n{ans_b[:1500]}\n\n"
            "Return JSON."
        )
        data, j_in, j_out, _ = await complete_json(
            client, user=payload, system=PICK_SYSTEM, model=j_model, max_tokens=128,
        )
        pick = str(data.get("pick", "B")).upper()
        final = ans_a if pick == "A" else ans_b

        total_in = a_in + b_in + j_in
        total_out = a_out + b_out + j_out
        return final, time.time() - t0, total_in, total_out

    return ensemble_runner
