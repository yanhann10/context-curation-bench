"""Stage 2 — Hierarchical strategy.

Two-pass:
  1. Map: summarize each doc to a one-paragraph abstract (cached once per run).
  2. Route: pass the question + all abstracts + doc ids to the model, ask which
     doc_ids are relevant (returns JSON list).
  3. Expand: include only the selected docs (full text) in the final prompt.

Interface mirrors strategies_rag — returns an async prompt_fn usable by
run_strategy_async.
"""
from __future__ import annotations
import asyncio
import json

from openai import AsyncOpenAI


SUMMARY_SYSTEM = (
    "Summarize the document in 1-2 sentences (<=60 words). "
    "Preserve the concrete specifics that would let a reader decide whether "
    "this doc is relevant to a question: policy type, dollar amounts, time "
    "windows, audiences (new hires, managers), recency hints."
)


async def summarize_doc(client: AsyncOpenAI, doc: dict, model: str) -> str:
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM},
            {"role": "user", "content": doc["content"][:6000]},
        ],
        temperature=0.0,
    )
    return (resp.choices[0].message.content or "").strip()


async def summarize_all(client: AsyncOpenAI, docs: list[dict], model: str, concurrency: int = 8) -> dict[str, str]:
    sem = asyncio.Semaphore(concurrency)

    async def one(d):
        async with sem:
            s = await summarize_doc(client, d, model)
            return d["id"], s

    pairs = await asyncio.gather(*[one(d) for d in docs])
    return dict(pairs)


ROUTER_SYSTEM = (
    "You are a routing model. Given a user question and a catalog of document "
    "abstracts with IDs, return a JSON array of doc IDs (from the catalog) that "
    "are plausibly relevant to answering the question. Prefer precision over "
    "recall: return 2-5 ids. Return JSON ONLY, shape: "
    '{"doc_ids": ["...", "..."]}'
)


async def route_docs(
    client: AsyncOpenAI,
    question: str,
    summaries: dict[str, str],
    docs: list[dict],
    model: str,
    max_ids: int = 5,
) -> list[str]:
    by_id = {d["id"]: d for d in docs}
    catalog_lines = []
    for did, s in summaries.items():
        meta = by_id.get(did, {}).get("metadata", {})
        title = meta.get("title", did)
        ts = meta.get("timestamp", "")
        catalog_lines.append(f"- id={did} | title={title}{(' | ts=' + ts) if ts else ''}\n  {s}")
    catalog = "\n".join(catalog_lines)
    user = f"QUESTION: {question}\n\nCATALOG:\n{catalog}\n\nReturn JSON only."

    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": ROUTER_SYSTEM},
            {"role": "user", "content": user},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
        ids = list(data.get("doc_ids", []))
    except Exception:
        ids = []
    ids = [did for did in ids if did in by_id][:max_ids]
    if not ids:
        # Safety fallback: include all static docs, no slack.
        ids = [d["id"] for d in docs if d["type"] == "static"][:max_ids]
    return ids


def hierarchical_prompt(question: str, selected: list[dict]) -> str:
    parts = []
    for d in selected:
        title = d["metadata"].get("title", d["id"])
        src = d["metadata"].get("source", "")
        ts = d["metadata"].get("timestamp", "")
        header = f"--- {title} [{src}{(' @ ' + ts) if ts else ''}] ---"
        parts.append(f"{header}\n{d['content'][:5000]}")
    body = "\n\n".join(parts)
    return (
        "You are a helpful New Hire Onboarding assistant. "
        "Answer using ONLY the sources below. Prefer recent when they disagree. "
        "Cite source titles.\n\n"
        f"=== SELECTED SOURCES ({len(selected)}) ===\n{body}\n\n"
        f"=== QUESTION ===\n{question}"
    )


async def hierarchical_build_prompt_fn(
    client: AsyncOpenAI, docs: list[dict], router_model: str, summary_model: str,
    max_ids: int = 5,
):
    """Build the summary cache once; return an async prompt_fn(question, docs)."""
    summaries = await summarize_all(client, docs, summary_model)
    by_id = {d["id"]: d for d in docs}

    async def prompt_fn(q: str, _docs) -> str:
        ids = await route_docs(client, q, summaries, docs, router_model, max_ids=max_ids)
        selected = [by_id[i] for i in ids if i in by_id]
        return hierarchical_prompt(q, selected)

    return prompt_fn
