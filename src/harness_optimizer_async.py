"""Async Meta-Harness-inspired optimizer (Claude backend)."""
from __future__ import annotations
import asyncio
import json
from dataclasses import asdict

from anthropic import AsyncAnthropic

from .strategies import CurationSpec, meta_harness_optimized
from .harness_optimizer import baseline_spec, PROPOSER_SYSTEM, doc_catalog, failure_traces
from .evaluator_async import answer_question_async, judge_async
from .llm_client import complete_json


async def eval_spec_async(
    spec: CurationSpec,
    questions: list[dict],
    docs: list[dict],
    client: AsyncAnthropic,
    agent_model: str,
    judge_model: str,
    concurrency: int = 8,
) -> tuple[float, list[dict]]:
    sem = asyncio.Semaphore(concurrency)

    async def one(q):
        async with sem:
            prompt = meta_harness_optimized(q["question"], docs, spec)
            ans, _, _, _ = await answer_question_async(client, prompt, agent_model)
            quality, recency, note, _, _ = await judge_async(client, q, ans, judge_model)
            return {
                "qid": q["id"], "question": q["question"],
                "golden": q["golden_answer"], "category": q["category"],
                "answer": ans, "quality": quality, "recency": recency, "note": note,
            }

    records = await asyncio.gather(*[one(q) for q in questions])
    mean_q = sum(r["quality"] for r in records) / max(len(records), 1)
    return mean_q, list(records)


async def propose_async(
    client: AsyncAnthropic,
    current: CurationSpec,
    records: list[dict],
    docs: list[dict],
    proposer_model: str,
) -> tuple[CurationSpec, str]:
    catalog = doc_catalog(docs)
    traces = failure_traces(records)
    user = (
        f"AVAILABLE DOCS:\n{catalog}\n\n"
        f"CURRENT SPEC:\n{json.dumps(asdict(current), indent=2)}\n\n"
        f"FAILURES ON TRAIN SET:\n{traces}\n\n"
        "Propose ONE mutation now. Return JSON only."
    )
    data, _, _, _ = await complete_json(
        client, user=user, system=PROPOSER_SYSTEM, model=proposer_model,
        max_tokens=1024, temperature=0.4,
    )
    rationale = data.pop("rationale", "") if isinstance(data, dict) else ""
    try:
        fields = {
            k: v for k, v in (data or {}).items()
            if k in CurationSpec.__dataclass_fields__
        }
        return CurationSpec(**fields), rationale
    except Exception as e:
        return current, f"parse-error: {e}"


async def optimize_async(
    train_questions: list[dict],
    docs: list[dict],
    client: AsyncAnthropic,
    agent_model: str,
    judge_model: str,
    proposer_model: str,
    n_iter: int = 3,
    concurrency: int = 8,
) -> tuple[CurationSpec, list[dict]]:
    spec = baseline_spec(docs)
    score, records = await eval_spec_async(
        spec, train_questions, docs, client, agent_model, judge_model, concurrency,
    )
    history = [{"iter": 0, "score": round(score, 3), "spec": asdict(spec), "rationale": "baseline"}]
    print(f"[optimizer] iter 0 baseline score={score:.3f}")
    for i in range(1, n_iter + 1):
        candidate, rationale = await propose_async(
            client, spec, records, docs, proposer_model,
        )
        cand_score, cand_records = await eval_spec_async(
            candidate, train_questions, docs, client, agent_model, judge_model, concurrency,
        )
        kept = cand_score > score
        print(f"[optimizer] iter {i} proposed score={cand_score:.3f} "
              f"({'KEEP' if kept else 'reject'}) — {rationale[:100]}")
        history.append({
            "iter": i, "score": round(cand_score, 3),
            "spec": asdict(candidate), "rationale": rationale, "kept": kept,
        })
        if kept:
            spec, score, records = candidate, cand_score, cand_records
    return spec, history
