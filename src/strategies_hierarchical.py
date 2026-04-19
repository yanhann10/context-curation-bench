"""Stage 2 — Hierarchical strategy (Claude backend)."""
from __future__ import annotations
import asyncio
import hashlib
import json
from pathlib import Path

from anthropic import AsyncAnthropic

from .llm_client import complete_text, complete_json


SUMMARY_SYSTEM = (
    "Summarize the document in 1-2 sentences (<=60 words). "
    "Preserve specifics that would let a reader decide relevance: policy type, "
    "dollar amounts, time windows, audiences, recency hints."
)


async def summarize_doc(client: AsyncAnthropic, doc: dict, model: str) -> str:
    text, _, _, _ = await complete_text(
        client,
        user=doc["content"][:6000],
        system=SUMMARY_SYSTEM,
        model=model,
        max_tokens=200,
    )
    return text.strip()


async def summarize_all(
    client: AsyncAnthropic, docs: list[dict], model: str, concurrency: int = 8,
) -> dict[str, str]:
    sem = asyncio.Semaphore(concurrency)

    async def one(d):
        async with sem:
            s = await summarize_doc(client, d, model)
            return d["id"], s

    return dict(await asyncio.gather(*[one(d) for d in docs]))


ROUTER_SYSTEM = (
    "You are a routing model. Given a user question and a catalog of document "
    "abstracts with IDs, return a JSON object listing the relevant doc IDs "
    "(from the catalog). Prefer precision over recall: return 2-5 ids. "
    'Return JSON only, shape: {"doc_ids": ["...", "..."]}'
)


async def route_docs(
    client: AsyncAnthropic,
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

    data, _, _, _ = await complete_json(
        client, user=user, system=ROUTER_SYSTEM, model=model, max_tokens=256,
    )
    ids = list(data.get("doc_ids", [])) if isinstance(data, dict) else []
    ids = [did for did in ids if did in by_id][:max_ids]
    if not ids:
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


def _summaries_cache_key(docs: list[dict], model: str) -> str:
    """Stable hash over doc ids + content lengths + model name."""
    h = hashlib.sha256()
    h.update(model.encode())
    for d in sorted(docs, key=lambda x: x["id"]):
        h.update(d["id"].encode())
        h.update(str(len(d["content"])).encode())
    return h.hexdigest()[:12]


async def _load_or_summarize(
    client: AsyncAnthropic, docs: list[dict], model: str, concurrency: int,
    cache_path: Path | None,
) -> dict[str, str]:
    if cache_path is not None and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text())
            if all(d["id"] in cached for d in docs):
                print(f"[hier] loaded {len(cached)} cached summaries from {cache_path.name}")
                return cached
        except Exception as e:
            print(f"[hier] cache read failed ({e}); re-summarizing")
    summaries = await summarize_all(client, docs, model, concurrency=concurrency)
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
        print(f"[hier] wrote {len(summaries)} summaries to {cache_path.name}")
    return summaries


async def hierarchical_build_prompt_fn(
    client: AsyncAnthropic,
    docs: list[dict],
    router_model: str,
    summary_model: str,
    max_ids: int = 5,
    concurrency: int = 8,
    cache_dir: Path | None = None,
):
    cache_path = None
    if cache_dir is not None:
        key = _summaries_cache_key(docs, summary_model)
        cache_path = cache_dir / f"hier_summaries_{key}.json"
    summaries = await _load_or_summarize(
        client, docs, summary_model, concurrency=concurrency, cache_path=cache_path,
    )
    by_id = {d["id"]: d for d in docs}

    async def prompt_fn(q: str, _docs) -> str:
        ids = await route_docs(client, q, summaries, docs, router_model, max_ids=max_ids)
        selected = [by_id[i] for i in ids if i in by_id]
        return hierarchical_prompt(q, selected)

    return prompt_fn
