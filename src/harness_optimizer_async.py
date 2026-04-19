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
            quality, note, _, _ = await judge_async(client, q, ans, judge_model)
            return {
                "qid": q["id"], "question": q["question"],
                "golden": q["golden_answer"], "category": q["category"],
                "answer": ans, "quality": quality, "note": note,
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
    dev_questions: list[dict] | None = None,
) -> tuple[CurationSpec, list[dict]]:
    """Propose-mutate-score loop over CurationSpec.

    dev_questions: optional held-out dev split. If provided, each accepted
    (kept) candidate is also scored on the dev set so the history records
    train/dev pairs — exposes overfit without changing the optimization
    signal (we still optimize on train).
    """
    spec = baseline_spec(docs)
    score, records = await eval_spec_async(
        spec, train_questions, docs, client, agent_model, judge_model, concurrency,
    )
    dev_score = None
    if dev_questions:
        dev_score, _ = await eval_spec_async(
            spec, dev_questions, docs, client, agent_model, judge_model, concurrency,
        )
    history = [{
        "iter": 0, "train_score": round(score, 3),
        "dev_score": round(dev_score, 3) if dev_score is not None else None,
        "spec": asdict(spec), "rationale": "baseline",
    }]
    dev_str = f" dev={dev_score:.3f}" if dev_score is not None else ""
    print(f"[optimizer] iter 0 baseline train={score:.3f}{dev_str}")
    for i in range(1, n_iter + 1):
        candidate, rationale = await propose_async(
            client, spec, records, docs, proposer_model,
        )
        cand_score, cand_records = await eval_spec_async(
            candidate, train_questions, docs, client, agent_model, judge_model, concurrency,
        )
        kept = cand_score > score
        # Dev-score every candidate (not just kept) so we see overfit candidates too.
        cand_dev = None
        if dev_questions:
            cand_dev, _ = await eval_spec_async(
                candidate, dev_questions, docs, client, agent_model, judge_model, concurrency,
            )
        dev_str = f" dev={cand_dev:.3f}" if cand_dev is not None else ""
        print(f"[optimizer] iter {i} proposed train={cand_score:.3f}{dev_str} "
              f"({'KEEP' if kept else 'reject'}) — {rationale[:100]}")
        history.append({
            "iter": i, "train_score": round(cand_score, 3),
            "dev_score": round(cand_dev, 3) if cand_dev is not None else None,
            "spec": asdict(candidate), "rationale": rationale, "kept": kept,
        })
        if kept:
            spec, score, records = candidate, cand_score, cand_records
    return spec, history
