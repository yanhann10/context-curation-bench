"""Harness variants for mle-bench: how much context the agent sees up front.

Each harness_fn: async (ctx, comp_id, public_dir) -> {code, prompt_tokens, completion_tokens, cost_usd}

Harnesses:
  - full_context:   description + data head + sample_submission in one prompt
  - hierarchical:   LLM-summarized description + file schema only (no data peek)
  - agent_managed:  tool-use loop (list_files, preview, read_text)
  - rag_embedding:  first+last 1k chars of description (proxy for retrieved chunks)
  - rerank_rag:     LLM scores description chunks for task-relevance, keep top-k
  - compressed:     LLM compresses description ~50% preserving metric/target/format
  - thin_harness:   file list + sample_submission only, no description (ablation floor)
"""
from __future__ import annotations
import json
import os
import re
from pathlib import Path

from anthropic import AsyncAnthropicBedrock


MODEL = os.getenv("XCMLE_MODEL", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
PRICE_IN = 3.00 / 1_000_000
PRICE_OUT = 15.00 / 1_000_000


def _client():
    return AsyncAnthropicBedrock(
        aws_region=os.getenv("AWS_REGION", "us-east-1"),
        max_retries=10,
        timeout=180,
    )


def _cost(in_tok: int, out_tok: int) -> float:
    return in_tok * PRICE_IN + out_tok * PRICE_OUT


def _read_head(path: Path, n: int = 50, max_chars: int = 4000) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            lines = [next(f) for _ in range(n)]
    except StopIteration:
        pass
    except Exception:
        return ""
    text = "".join(lines)
    return text[:max_chars]


def _list_files(public_dir: Path) -> list[dict]:
    out = []
    for p in sorted(public_dir.iterdir()):
        if p.is_file():
            out.append({"name": p.name, "size": p.stat().st_size})
    return out


def _extract_code(text: str) -> str:
    m = re.search(r"```python\s*\n([\s\S]*?)```", text)
    if m:
        return m.group(1)
    m = re.search(r"```\s*\n([\s\S]*?)```", text)
    if m:
        return m.group(1)
    return text.strip()


SYSTEM = (
    "You are an expert Kaggle ML engineer. You will be given a competition "
    "description and data files. Produce a single self-contained Python script "
    "that reads data from /data/public/, trains a reasonable model, and writes "
    "predictions to /workspace/submission.csv in the format shown by "
    "sample_submission.csv. "
    "Keep runtime under 5 minutes. Use only libraries likely present: "
    "pandas, numpy, scikit-learn. Do NOT call the internet. Do NOT import "
    "packages that require GPU. "
    "Output ONLY the Python code in a ```python fenced block. No prose."
)


async def _generate(client, system: str, user: str) -> dict:
    resp = await client.messages.create(
        model=MODEL, max_tokens=4096, temperature=0.0,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    return {
        "code": _extract_code(text),
        "prompt_tokens": resp.usage.input_tokens,
        "completion_tokens": resp.usage.output_tokens,
        "cost_usd": _cost(resp.usage.input_tokens, resp.usage.output_tokens),
    }


async def full_context(ctx, comp_id: str, public_dir: Path) -> dict:
    desc = (public_dir / "description.md").read_text(encoding="utf-8", errors="ignore")
    files = _list_files(public_dir)
    previews = []
    for f in files:
        if f["name"].endswith(".csv"):
            p = public_dir / f["name"]
            n = 5 if f["name"].startswith("test") else 50
            previews.append(f"### `{f['name']}` (first {n} lines)\n```\n{_read_head(p, n=n, max_chars=3000)}```")
    sample_sub = ""
    ss = public_dir / "sample_submission.csv"
    if ss.exists():
        sample_sub = f"\n\nFull `sample_submission.csv` (required output format):\n```\n{ss.read_text()[:2000]}```"

    user = (
        f"# Competition: {comp_id}\n\n"
        f"## Task description\n\n{desc}\n\n"
        f"## Files available in `/data/public/`\n"
        + "\n".join(f"- {f['name']} ({f['size']} bytes)" for f in files)
        + "\n\n## Data previews\n\n"
        + "\n\n".join(previews)
        + sample_sub
        + "\n\nWrite the solution now."
    )
    client = _client()
    return await _generate(client, SYSTEM, user)


async def hierarchical(ctx, comp_id: str, public_dir: Path) -> dict:
    """Summarize description to bullets, give only file schema + columns, no data peek."""
    desc = (public_dir / "description.md").read_text(encoding="utf-8", errors="ignore")
    files = _list_files(public_dir)

    # First call: summarize the description
    client = _client()
    summary_prompt = (
        f"Summarize this Kaggle competition brief into 4 bullets: task, input, "
        f"target variable, evaluation metric. Max 30 words per bullet.\n\n{desc[:6000]}"
    )
    summ_resp = await client.messages.create(
        model=MODEL, max_tokens=300, temperature=0.0,
        messages=[{"role": "user", "content": summary_prompt}],
    )
    summary = "".join(b.text for b in summ_resp.content if getattr(b, "type", "") == "text")
    summary_cost = _cost(summ_resp.usage.input_tokens, summ_resp.usage.output_tokens)
    in_tok = summ_resp.usage.input_tokens
    out_tok = summ_resp.usage.output_tokens

    # File schemas: column names + dtype hints via first-line only
    schemas = []
    for f in files:
        if f["name"].endswith(".csv"):
            head = _read_head(public_dir / f["name"], n=2, max_chars=500)
            cols = head.split("\n")[0] if head else ""
            schemas.append(f"- `{f['name']}` — columns: `{cols}`")

    user = (
        f"# Competition: {comp_id}\n\n"
        f"## Summary\n{summary}\n\n"
        f"## Files (schemas only, no data shown)\n"
        + "\n".join(schemas)
        + f"\n\nThe full files live at `/data/public/`. Write a Python solution."
    )
    gen = await _generate(client, SYSTEM, user)
    gen["prompt_tokens"] += in_tok
    gen["completion_tokens"] += out_tok
    gen["cost_usd"] += summary_cost
    return gen


async def rag_embedding(ctx, comp_id: str, public_dir: Path) -> dict:
    """Approximation: give only first and last 1000 chars of the description
    (no data preview, no summarization). Proxy for 'retrieved relevant chunks'.
    """
    desc = (public_dir / "description.md").read_text(encoding="utf-8", errors="ignore")
    files = _list_files(public_dir)
    excerpt = desc[:1000] + "\n\n[...middle omitted...]\n\n" + desc[-1000:] if len(desc) > 2500 else desc
    user = (
        f"# Competition: {comp_id}\n\n"
        f"## Retrieved description excerpts\n{excerpt}\n\n"
        f"## Files\n"
        + "\n".join(f"- {f['name']}" for f in files)
        + "\n\nWrite the solution."
    )
    client = _client()
    return await _generate(client, SYSTEM, user)


async def agent_managed(ctx, comp_id: str, public_dir: Path) -> dict:
    """Tool-use loop. Agent gets tools to list/preview files, then emits code."""
    client = _client()

    def list_files_tool(**_):
        return json.dumps(_list_files(public_dir))

    def preview_tool(filename: str, n: int = 10, **_):
        p = public_dir / filename
        if not p.exists():
            return json.dumps({"error": f"no such file: {filename}"})
        return _read_head(p, n=n, max_chars=3000)

    def read_text_tool(filename: str, **_):
        p = public_dir / filename
        if not p.exists():
            return json.dumps({"error": f"no such file: {filename}"})
        return p.read_text(encoding="utf-8", errors="ignore")[:8000]

    tools = [
        {"name": "list_files", "description": "List all files in /data/public/ with sizes. No args.",
         "input_schema": {"type": "object", "properties": {}}},
        {"name": "preview_file", "description": "Preview first N lines of a file.",
         "input_schema": {"type": "object",
                          "properties": {"filename": {"type": "string"},
                                         "n": {"type": "integer", "default": 10}},
                          "required": ["filename"]}},
        {"name": "read_text_file", "description": "Read full text of a small file (e.g. description.md).",
         "input_schema": {"type": "object",
                          "properties": {"filename": {"type": "string"}},
                          "required": ["filename"]}},
    ]
    messages = [{"role": "user", "content": (
        f"Solve Kaggle competition `{comp_id}`. Data lives at `/data/public/`. "
        f"Use the tools to inspect the task + files, then emit ONE final "
        f"Python script in a ```python fenced block that writes "
        f"/workspace/submission.csv. Keep runtime under 5 minutes. "
        f"Do not call the internet."
    )}]

    in_tok_total = 0
    out_tok_total = 0
    final_text = ""
    TOOL_MAP = {"list_files": list_files_tool, "preview_file": preview_tool, "read_text_file": read_text_tool}

    for _ in range(8):
        resp = await client.messages.create(
            model=MODEL, max_tokens=4096, temperature=0.0,
            system=SYSTEM, tools=tools, messages=messages,
        )
        in_tok_total += resp.usage.input_tokens
        out_tok_total += resp.usage.output_tokens
        turn_text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        if turn_text:
            final_text = turn_text

        if resp.stop_reason != "tool_use":
            break

        messages.append({"role": "assistant", "content": resp.content})
        tool_results = []
        for block in resp.content:
            if getattr(block, "type", "") == "tool_use":
                fn = TOOL_MAP.get(block.name)
                try:
                    out = fn(**(block.input or {})) if fn else json.dumps({"error": f"unknown tool {block.name}"})
                except Exception as e:
                    out = json.dumps({"error": f"tool exec: {e}"})
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
        if not tool_results:
            break
        messages.append({"role": "user", "content": tool_results})

    return {
        "code": _extract_code(final_text),
        "prompt_tokens": in_tok_total,
        "completion_tokens": out_tok_total,
        "cost_usd": _cost(in_tok_total, out_tok_total),
    }


def _chunk_text(text: str, max_chars: int = 500) -> list[str]:
    """Split text into chunks of ~max_chars, preferring paragraph boundaries."""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paras:
        if not buf:
            buf = p
        elif len(buf) + 2 + len(p) <= max_chars:
            buf = buf + "\n\n" + p
        else:
            chunks.append(buf)
            buf = p
        if len(buf) >= max_chars:
            chunks.append(buf)
            buf = ""
    if buf:
        chunks.append(buf)
    return chunks


async def rerank_rag(ctx, comp_id: str, public_dir: Path) -> dict:
    """Chunk description, LLM scores each chunk for task-relevance, keep top-k.

    If description is short (<2500 chars), degrades to full inclusion.
    """
    desc = (public_dir / "description.md").read_text(encoding="utf-8", errors="ignore")
    files = _list_files(public_dir)
    sample_sub = ""
    ss = public_dir / "sample_submission.csv"
    if ss.exists():
        sample_sub = f"\n\nFull `sample_submission.csv` (required output format):\n```\n{ss.read_text()[:2000]}```"

    client = _client()
    in_tok = 0
    out_tok = 0
    cost = 0.0

    chunks = _chunk_text(desc, max_chars=500)
    if len(chunks) <= 3:
        excerpt = desc
    else:
        labeled = "\n\n".join(f"[chunk {i}]\n{c}" for i, c in enumerate(chunks))
        rerank_prompt = (
            "Score each chunk 0-10 on relevance for writing a Kaggle solution "
            "(task, target, metric, format are most relevant; motivation/history "
            "less so). Respond as JSON: {\"scores\": [int, int, ...]} — one per "
            f"chunk, in order. There are {len(chunks)} chunks.\n\n{labeled}"
        )
        rr = await client.messages.create(
            model=MODEL, max_tokens=1024, temperature=0.0,
            messages=[{"role": "user", "content": rerank_prompt}],
        )
        in_tok += rr.usage.input_tokens
        out_tok += rr.usage.output_tokens
        cost += _cost(rr.usage.input_tokens, rr.usage.output_tokens)
        raw = "".join(b.text for b in rr.content if getattr(b, "type", "") == "text")
        try:
            m = re.search(r"\{[\s\S]*\}", raw)
            scores = json.loads(m.group(0))["scores"] if m else []
        except Exception:
            scores = []
        if len(scores) != len(chunks):
            scores = [1] * len(chunks)
        k = min(5, len(chunks))
        top_idx = sorted(sorted(range(len(chunks)), key=lambda i: -scores[i])[:k])
        excerpt = "\n\n".join(chunks[i] for i in top_idx)

    user = (
        f"# Competition: {comp_id}\n\n"
        f"## Task description (reranked excerpts)\n{excerpt}\n\n"
        f"## Files available in `/data/public/`\n"
        + "\n".join(f"- {f['name']} ({f['size']} bytes)" for f in files)
        + sample_sub
        + "\n\nWrite the solution now."
    )
    gen = await _generate(client, SYSTEM, user)
    gen["prompt_tokens"] += in_tok
    gen["completion_tokens"] += out_tok
    gen["cost_usd"] += cost
    return gen


async def compressed(ctx, comp_id: str, public_dir: Path) -> dict:
    """LLM compresses description ~50% length, preserving metric/target/format.

    Tests token-budget compression (LLMLingua-style axis).
    """
    desc = (public_dir / "description.md").read_text(encoding="utf-8", errors="ignore")
    files = _list_files(public_dir)
    sample_sub = ""
    ss = public_dir / "sample_submission.csv"
    if ss.exists():
        sample_sub = f"\n\nFull `sample_submission.csv`:\n```\n{ss.read_text()[:2000]}```"

    client = _client()
    target_len = max(500, len(desc) // 2)
    compress_prompt = (
        f"Compress this Kaggle competition description to approximately "
        f"{target_len} characters. Preserve EXACTLY: task type, input columns, "
        f"target variable, evaluation metric, submission format. Drop motivation, "
        f"history, examples. Output just the compressed description, no preamble.\n\n"
        f"{desc}"
    )
    cr = await client.messages.create(
        model=MODEL, max_tokens=2048, temperature=0.0,
        messages=[{"role": "user", "content": compress_prompt}],
    )
    compressed_desc = "".join(b.text for b in cr.content if getattr(b, "type", "") == "text")
    in_tok = cr.usage.input_tokens
    out_tok = cr.usage.output_tokens
    cost = _cost(in_tok, out_tok)

    user = (
        f"# Competition: {comp_id}\n\n"
        f"## Task description (compressed)\n{compressed_desc}\n\n"
        f"## Files available in `/data/public/`\n"
        + "\n".join(f"- {f['name']} ({f['size']} bytes)" for f in files)
        + sample_sub
        + "\n\nWrite the solution now."
    )
    gen = await _generate(client, SYSTEM, user)
    gen["prompt_tokens"] += in_tok
    gen["completion_tokens"] += out_tok
    gen["cost_usd"] += cost
    return gen


async def thin_harness(ctx, comp_id: str, public_dir: Path) -> dict:
    """File list + sample_submission only. No description. Ablation floor."""
    files = _list_files(public_dir)
    sample_sub = ""
    ss = public_dir / "sample_submission.csv"
    if ss.exists():
        sample_sub = f"\n\nSample submission:\n```\n{ss.read_text()[:1500]}```"

    user = (
        f"# Kaggle competition: `{comp_id}`\n\n"
        f"## Files available in `/data/public/`\n"
        + "\n".join(f"- {f['name']} ({f['size']} bytes)" for f in files)
        + sample_sub
        + "\n\nInfer the task from the file names + sample submission format. "
        + "Write the Python solution."
    )
    client = _client()
    return await _generate(client, SYSTEM, user)


HARNESSES = {
    "full_context": full_context,
    "rag_embedding": rag_embedding,
    "hierarchical": hierarchical,
    "agent_managed": agent_managed,
    "rerank_rag": rerank_rag,
    "compressed": compressed,
    "thin_harness": thin_harness,
}
