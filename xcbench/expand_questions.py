"""Expand questions JSONL to target size by LLM-generating new goldens.

  python -m xcbench.expand_questions --target 100 --out data/questions.jsonl

Strategy:
  - Read the existing corpus.jsonl (static + fresh docs).
  - Read the current questions.jsonl as seed exemplars.
  - For each of 4 categories (portal_only, slack_contradicts, slack_only,
    needs_both), prompt the LLM with: relevant docs + category definition
    + seed exemplars + "generate K new questions as JSON".
  - Target distribution: 25 portal_only, 40 slack_contradicts, 20 slack_only,
    15 needs_both (slack_contradicts is the hardest + most interesting).
  - Dedupe by normalized question text. Merge with seeds, write out.

Uses the same backend switch as `xcbench run`. Bedrock-friendly.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .backend import make_client, resolve_model
from .corpus import load_jsonl
from .dataset import load_questions

TARGET_DIST = {
    "portal_only": 0.25,
    "slack_contradicts": 0.40,
    "slack_only": 0.20,
    "needs_both": 0.15,
}

CATEGORY_DEFS = {
    "portal_only":
        "answerable purely from the static handbook; the slack corpus does "
        "not touch this topic. Golden should quote handbook-specific values.",
    "slack_contradicts":
        "handbook has a stale value; a recent Slack thread (HR-validated) "
        "has the current correct value. Golden must prefer the Slack value "
        "and explicitly note the handbook is stale.",
    "slack_only":
        "info only appears in a Slack thread; handbook is silent. Golden "
        "should cite the Slack thread.",
    "needs_both":
        "handbook gives the policy/framework; Slack gives a current "
        "clarifying detail. Golden needs to combine both.",
}

GEN_SYSTEM = (
    "You are writing evaluation questions over a provided corpus of static "
    "reference documents and recent discussion threads. Produce realistic "
    "end-user questions with golden answers. "
    "Questions must be answerable from the docs shown. "
    "Goldens must be concrete (specific values, durations, named steps, "
    "etc., drawn from the corpus). Avoid vague phrasings. Do NOT repeat "
    "any seed question. "
    "Return STRICT JSON only, an array of objects with shape: "
    '{"question": str, "golden_answer": str, '
    '"key_facts": [str, str, ...], "relevant_source_ids": [str, ...]}'
)


def _render_doc_catalog(docs, kind: str, limit_chars: int = 1500) -> str:
    lines = []
    for d in docs:
        if kind and d.kind != kind:
            continue
        body = d.content[:limit_chars].replace("\n", " ")
        lines.append(f"[{d.id}] ({d.kind}, ts={d.timestamp}) {d.title}\n  {body}")
    return "\n\n".join(lines)


def _render_seeds(seeds, category: str) -> str:
    relevant = [q for q in seeds if q.category == category][:3]
    if not relevant:
        return "(no seeds in this category yet)"
    out = []
    for q in relevant:
        out.append(json.dumps({
            "question": q.input,
            "golden_answer": q.golden[:500],
            "key_facts": q.key_facts[:3],
            "relevant_source_ids": q.relevant_doc_ids,
        }, ensure_ascii=False))
    return "\n".join(out)


async def _gen_for_category(client, model, category: str, n: int, corpus, seeds) -> list[dict]:
    if category in ("slack_contradicts", "slack_only", "needs_both"):
        catalog = _render_doc_catalog(corpus.docs, kind="")
    else:
        catalog = _render_doc_catalog(corpus.docs, kind="static")

    seed_block = _render_seeds(seeds, category)
    prompt = (
        f"CATEGORY: {category}\n"
        f"DEFINITION: {CATEGORY_DEFS[category]}\n\n"
        f"CORPUS:\n{catalog}\n\n"
        f"SEED EXAMPLES IN THIS CATEGORY:\n{seed_block}\n\n"
        f"Generate {n} NEW questions of this category. "
        f"Do not repeat any seed question. "
        f"For slack_contradicts / slack_only / needs_both, include the "
        f"relevant slack thread id in relevant_source_ids. "
        f"Return a JSON ARRAY of {n} objects. No prose outside the JSON."
    )
    resp = await client.messages.create(
        model=model, max_tokens=8192, temperature=0.7,
        system=GEN_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    items = _extract_json_array(text)
    if not items:
        print(f"[WARN] {category}: no parseable items; text[:200]={text[:200]!r}")
        return []
    out = []
    for i, it in enumerate(items):
        if not isinstance(it, dict) or "question" not in it or "golden_answer" not in it:
            continue
        out.append({
            "question": it["question"],
            "golden_answer": it["golden_answer"],
            "category": category,
            "key_facts": list(it.get("key_facts", []))[:6],
            "relevant_source_ids": list(it.get("relevant_source_ids", [])),
        })
    print(f"[gen] {category}: requested {n}, got {len(out)}  "
          f"(usage in={resp.usage.input_tokens} out={resp.usage.output_tokens})")
    return out


def _normalize_q(q: str) -> str:
    return re.sub(r"\s+", " ", q.strip().lower())


def _extract_json_array(text: str) -> list[dict]:
    """Tolerate a truncated JSON array by greedily extracting each object.

    Walks the text, tracks brace depth while respecting strings/escapes,
    and parses each top-level object independently. Any final malformed
    object (e.g. truncated by max_tokens) is simply dropped.
    """
    m = re.search(r"\[", text)
    if m is None:
        return []
    s = text[m.start():]
    out: list[dict] = []
    depth = 0
    in_str = False
    esc = False
    start_idx = None
    for i, ch in enumerate(s):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            if depth == 0:
                start_idx = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start_idx is not None:
                chunk = s[start_idx : i + 1]
                try:
                    out.append(json.loads(chunk))
                except Exception:
                    pass
                start_idx = None
    return out


async def amain(args) -> int:
    load_dotenv(Path(".env"))
    client, backend = make_client()
    model = resolve_model(args.model, backend)
    print(f"backend={backend}  model={model}")

    corpus = load_jsonl(args.corpus)
    seeds = load_questions(args.seed)
    print(f"corpus={len(corpus.docs)} docs  seeds={len(seeds)}")

    seen = {_normalize_q(q.input) for q in seeds}
    existing_by_cat: dict[str, list] = {c: [] for c in TARGET_DIST}
    for q in seeds:
        if q.category in existing_by_cat:
            existing_by_cat[q.category].append(q)

    # compute how many to generate per category
    needed: dict[str, int] = {}
    for cat, frac in TARGET_DIST.items():
        want = int(round(args.target * frac))
        have = len(existing_by_cat[cat])
        needed[cat] = max(0, want - have)

    print(f"targets: {needed}")

    tasks = [
        _gen_for_category(client, model, cat, n, corpus, seeds)
        for cat, n in needed.items() if n > 0
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    new_rows: list[dict] = []
    for r in results:
        if isinstance(r, Exception):
            print(f"[ERROR] {r}")
            continue
        for item in r:
            key = _normalize_q(item["question"])
            if key in seen:
                continue
            seen.add(key)
            new_rows.append(item)

    # assign IDs
    max_existing_id = 0
    for q in seeds:
        m = re.search(r"(\d+)$", q.id)
        if m:
            max_existing_id = max(max_existing_id, int(m.group(1)))
    for i, row in enumerate(new_rows, start=max_existing_id + 1):
        row["id"] = f"q-exp-{i:03d}"

    # merge with seeds, write out
    seed_rows = []
    for q in seeds:
        seed_rows.append({
            "id": q.id,
            "input": q.input,
            "golden": q.golden,
            "category": q.category,
            "key_facts": q.key_facts,
            "relevant_doc_ids": q.relevant_doc_ids,
            "relevant_slices": q.relevant_slices,
        })

    merged = list(seed_rows)
    for r in new_rows:
        merged.append({
            "id": r["id"],
            "input": r["question"],
            "golden": r["golden_answer"],
            "category": r["category"],
            "key_facts": r["key_facts"],
            "relevant_doc_ids": r["relevant_source_ids"],
            "relevant_slices": (
                ["handbook"] if r["category"] == "portal_only"
                else ["slack"] if r["category"] == "slack_only"
                else ["handbook", "slack"]
            ),
        })

    out = Path(args.out)
    out.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in merged) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {out}  ({len(merged)} questions = {len(seeds)} seed + {len(new_rows)} new)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="data/corpus.jsonl")
    ap.add_argument("--seed", default="data/questions.jsonl")
    ap.add_argument("--out", default="data/questions.jsonl")
    ap.add_argument("--target", type=int, default=100)
    ap.add_argument("--model", default="claude-sonnet-4-6")
    args = ap.parse_args()
    return asyncio.run(amain(args))


if __name__ == "__main__":
    sys.exit(main())
