"""Cascade routing: cheap-first with self-verification escalation.

Tier 1: hierarchical (~$0.012/q, 91.5% quality on HR)
  → self-verify the answer ("confident? 0|1")
  → if confident=1: return it
Tier 2: agent_managed (~$0.032/q, 99.5% quality)
  → self-verify again
  → if still confident=0: escalate
Tier 3: full_context (~$0.067/q, 100% quality on HR)

Tokens summed across all tiers + verifications. Returns same shape as
answer_question_async so evaluator_async.run_agent_strategy_async can consume it.
"""
from __future__ import annotations
import time

from anthropic import AsyncAnthropic

from .llm_client import complete_json, complete_text
from .evaluator_async import answer_question_async
from .strategies import full_context
from .strategies_agent_managed import agent_managed_runner


VERIFY_SYSTEM = (
    "You are a verification model. Given a question and an answer, decide "
    "whether the answer is CONFIDENT (fully addresses the question with specific "
    "grounded facts, cites sources, no hedging, no domain-refusal) or "
    "NOT CONFIDENT (vague, missing key facts, heavy hedging, refusing based on "
    "domain assumptions instead of checking sources, or specific-wrong-fact patterns "
    "like unsupported numbers). Read the answer skeptically — do not trust surface "
    "features like citation brackets or specific numbers; check whether claims are "
    "substantive and coherent. "
    'Return JSON only: {"confident": 0|1, "reason": "<short, <=80 chars>"}'
)


async def _verify(
    client: AsyncAnthropic, question: str, answer: str, model: str,
) -> tuple[int, str, int, int]:
    if not answer.strip():
        return 0, "empty answer", 0, 0
    payload = f"Question: {question}\n\nAnswer: {answer[:1500]}\n\nReturn JSON."
    data, in_tok, out_tok, _ = await complete_json(
        client, user=payload, system=VERIFY_SYSTEM, model=model, max_tokens=128,
    )
    try:
        c = 1 if int(data.get("confident", 0)) else 0
        reason = str(data.get("reason", ""))[:80]
        return c, reason, in_tok, out_tok
    except Exception as e:
        return 0, f"parse-error: {e}", in_tok, out_tok


def make_cascade_runner(
    hier_prompt_fn,
    final_fallback: str = "agent",
    verifier_model: str | None = None,
    domain_description: str | None = None,
):
    """Factory returning a runner compatible with run_agent_strategy_async.

    hier_prompt_fn: async (question, docs) -> prompt_str, from hierarchical_build_prompt_fn
    final_fallback: "agent" (stop at tier 2) or "full" (add tier 3 = full_context)
    verifier_model: if provided, use a DIFFERENT model for self-verification — this
        mitigates the self-confidence blind spot documented on HR q-v2-010 and
        Polars q-polars-007, where the same-model verifier trusted a confidently-wrong
        tier-1 answer. Pass e.g. `claude-haiku-4-5` while the answerer is `sonnet-4-6`.
    domain_description: optional corpus hint forwarded to agent_managed (tier 2).
    """
    async def cascade_runner(
        client: AsyncAnthropic, question: str, docs: list[dict], model: str,
    ) -> tuple[str, float, int, int]:
        v_model = verifier_model or model
        t0 = time.time()
        in_total = 0
        out_total = 0

        # Tier 1: hierarchical
        hier_prompt = await hier_prompt_fn(question, docs)
        ans1, _, h_in, h_out = await answer_question_async(client, hier_prompt, model)
        in_total += h_in; out_total += h_out

        c1, _, v1_in, v1_out = await _verify(client, question, ans1, v_model)
        in_total += v1_in; out_total += v1_out
        if c1:
            return ans1, time.time() - t0, in_total, out_total

        # Tier 2: agent_managed
        ans2, _, a_in, a_out = await agent_managed_runner(
            client, question, docs, model, domain_description=domain_description,
        )
        in_total += a_in; out_total += a_out

        if final_fallback != "full":
            return ans2, time.time() - t0, in_total, out_total

        c2, _, v2_in, v2_out = await _verify(client, question, ans2, v_model)
        in_total += v2_in; out_total += v2_out
        if c2:
            return ans2, time.time() - t0, in_total, out_total

        # Tier 3: full_context
        fc_prompt = full_context(question, docs)
        ans3, _, f_in, f_out = await answer_question_async(client, fc_prompt, model)
        in_total += f_in; out_total += f_out
        return ans3, time.time() - t0, in_total, out_total

    return cascade_runner
