"""Synchronous helpers + baseline spec for the Meta-Harness-inspired optimizer.

The live optimize() loop is in harness_optimizer_async.py (Claude backend).
This module only holds stateless helpers reused by the async path.
"""
from __future__ import annotations

from .strategies import CurationSpec


PROPOSER_SYSTEM = """You are optimizing an agent's context curation strategy.

You are given:
  - the current CurationSpec (which documents to include, in what order, how to format)
  - the full list of available document ids (static reference docs + recent discussion threads)
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
    return CurationSpec(
        include_static_ids=[d["id"] for d in docs if d["type"] == "static"],
        include_slack_ids=[d["id"] for d in docs if d["type"] == "slack"],
        ordering="static_first",
        doc_format="titled",
        prepend_instructions=(
            "Answer using ONLY the provided sources. "
            "Prefer the most recent source when sources disagree. Cite source titles."
        ),
        max_chars_per_doc=3000,
    )


def doc_catalog(docs: list[dict]) -> str:
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


def failure_traces(records: list[dict], min_quality: float = 0.75) -> str:
    fails = [r for r in records if r["quality"] < min_quality]
    if not fails:
        return "(no failures at current quality threshold)"
    lines = []
    for r in fails:
        lines.append(
            f"- qid={r['qid']} [{r['category']}] q={r['quality']:.2f}\n"
            f"  question: {r['question']}\n"
            f"  golden:   {r['golden']}\n"
            f"  answer:   {r['answer'][:350].replace(chr(10), ' ')}\n"
            f"  judge:    {r['note']}"
        )
    return "\n".join(lines)
