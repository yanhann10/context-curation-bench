"""Lightweight Meta-Harness-inspired optimizer for CurationSpec.

Faithful Meta-Harness mutates harness *code* using execution traces + filesystem.
For a 2hr hackathon we compress that to: mutate a typed CurationSpec using
failure traces from a train set. Same loop shape, much safer execution,
interpretable output.

Loop:
  spec = baseline(docs)
  score = eval(spec, train_qs)
  repeat n_iter:
    traces = collect_failures(spec, train_qs)
    candidate = propose_mutation(spec, traces, all_doc_ids)
    score_c = eval(candidate, train_qs)
    if score_c > score: spec, score = candidate, score_c
  return spec, history
"""
from __future__ import annotations
import json
from dataclasses import asdict
from typing import Callable

from openai import OpenAI

from .strategies import CurationSpec, meta_harness_optimized


PROPOSER_SYSTEM = """You are optimizing a New Hire Onboarding Agent's context curation strategy.

You are given:
  - the current CurationSpec (which documents to include, in what order, how to format)
  - the full list of available document ids (static handbook + slack threads)
  - failure traces from a train set (questions the current spec got wrong, with the golden answer)

Your job: propose ONE mutation to the CurationSpec that plausibly addresses the failures. Mutations you can make:
  - change include_static_ids (subset)
  - change include_slack_ids (subset)  [hint: Slack threads often update stale handbook policy]
  - change ordering ("as_is" | "static_first" | "slack_first" | "recency_first")
  - change doc_format ("raw" | "titled" | "structured")
  - change max_chars_per_doc (int 500..8000)
  - change prepend_instructions (short string, 0..400 chars)

Return STRICT JSON with the full new spec. No prose, no markdown. Keys exactly:
{
  "include_static_ids": [...],
  "include_slack_ids": [...],
  "ordering": "...",
  "doc_format": "...",
  "max_chars_per_doc": int,
  "prepend_instructions": "...",
  "rationale": "<one-sentence reason for this mutation>"
}
"""


def baseline_spec(docs: list[dict]) -> CurationSpec:
    """Naive default: include everything, static first, titled format."""
    return CurationSpec(
        include_static_ids=[d["id"] for d in docs if d["type"] == "static"],
        include_slack_ids=[d["id"] for d in docs if d["type"] == "slack"],
        ordering="static_first",
        doc_format="titled",
        prepend_instructions=(
            "You are a helpful New Hire Onboarding assistant. "
            "Prefer the most recent source when sources disagree. Cite source titles."
        ),
        max_chars_per_doc=3000,
    )


def eval_spec(
    spec: CurationSpec,
    questions: list[dict],
    docs: list[dict],
    client: OpenAI,
    agent_model: str,
    judge_model: str,
    answer_fn: Callable,
    judge_fn: Callable,
) -> tuple[float, list[dict]]:
    """Return (mean_quality, per_question_records)."""
    records = []
    for q in questions:
        prompt = meta_harness_optimized(q["question"], docs, spec)
        answer, latency, in_tok, out_tok = answer_fn(client, prompt, agent_model)
        quality, recency, note = judge_fn(client, q, answer, judge_model)
        records.append({
            "qid": q["id"],
            "question": q["question"],
            "golden": q["golden_answer"],
            "category": q["category"],
            "answer": answer,
            "quality": quality,
            "recency": recency,
            "note": note,
        })
    mean_q = sum(r["quality"] for r in records) / max(len(records), 1)
    return mean_q, records


def _failure_traces(records: list[dict], min_quality: float = 0.75) -> str:
    fails = [r for r in records if r["quality"] < min_quality]
    if not fails:
        return "(no failures at current quality threshold)"
    lines = []
    for r in fails:
        lines.append(
            f"- qid={r['qid']} [{r['category']}] q={r['quality']:.2f} r={r['recency']}\n"
            f"  question: {r['question']}\n"
            f"  golden:   {r['golden']}\n"
            f"  answer:   {r['answer'][:350].replace(chr(10), ' ')}\n"
            f"  judge:    {r['note']}"
        )
    return "\n".join(lines)


def _doc_catalog(docs: list[dict]) -> str:
    lines = []
    for d in docs:
        title = d["metadata"].get("title", "")
        rel = d["metadata"].get("relationship", "")
        ts = d["metadata"].get("timestamp", "")
        lines.append(
            f"  {d['id']} [{d['type']}]"
            f"{' @' + ts if ts else ''}"
            f"{' rel=' + rel if rel else ''}"
            f": {title}"
        )
    return "\n".join(lines)


def propose(
    client: OpenAI,
    current: CurationSpec,
    records: list[dict],
    docs: list[dict],
    proposer_model: str,
) -> tuple[CurationSpec, str]:
    catalog = _doc_catalog(docs)
    traces = _failure_traces(records)
    user = (
        f"AVAILABLE DOCS:\n{catalog}\n\n"
        f"CURRENT SPEC:\n{json.dumps(asdict(current), indent=2)}\n\n"
        f"FAILURES ON TRAIN SET:\n{traces}\n\n"
        "Propose ONE mutation now. Return JSON only."
    )
    resp = client.chat.completions.create(
        model=proposer_model,
        messages=[
            {"role": "system", "content": PROPOSER_SYSTEM},
            {"role": "user", "content": user},
        ],
        temperature=0.4,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
        rationale = data.pop("rationale", "")
        return CurationSpec(**{k: v for k, v in data.items() if k in CurationSpec.__dataclass_fields__}), rationale
    except Exception as e:
        # Fall back to current if the proposer misbehaves.
        return current, f"parse-error: {e}"


def optimize(
    train_questions: list[dict],
    docs: list[dict],
    client: OpenAI,
    agent_model: str,
    judge_model: str,
    proposer_model: str,
    answer_fn: Callable,
    judge_fn: Callable,
    n_iter: int = 3,
) -> tuple[CurationSpec, list[dict]]:
    spec = baseline_spec(docs)
    score, records = eval_spec(spec, train_questions, docs, client, agent_model, judge_model, answer_fn, judge_fn)
    history = [{"iter": 0, "score": round(score, 3), "spec": asdict(spec), "rationale": "baseline"}]
    print(f"[optimizer] iter 0 baseline score={score:.3f}")
    for i in range(1, n_iter + 1):
        candidate, rationale = propose(client, spec, records, docs, proposer_model)
        cand_score, cand_records = eval_spec(
            candidate, train_questions, docs, client, agent_model, judge_model, answer_fn, judge_fn
        )
        kept = cand_score > score
        print(f"[optimizer] iter {i} proposed score={cand_score:.3f} "
              f"({'KEEP' if kept else 'reject'}) — {rationale[:100]}")
        history.append({
            "iter": i,
            "score": round(cand_score, 3),
            "spec": asdict(candidate),
            "rationale": rationale,
            "kept": kept,
        })
        if kept:
            spec, score, records = candidate, cand_score, cand_records
    return spec, history
