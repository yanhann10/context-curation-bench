"""Agent-managed context (tool-use loop).

The model requests what it needs by calling tools. Tools:
  - list_handbook()                 -> [{id, title, timestamp}]
  - get_handbook(doc_id)            -> full text
  - list_slack()                    -> [{id, title, timestamp, channel, user}]
  - get_slack(thread_id)            -> full text

Loop stops when model returns end_turn, or at max_iterations.

Exposed entry:
  async def agent_managed_runner(client, question, docs, model, max_iter=6)
    -> (answer_text, latency_s, prompt_tokens_total, completion_tokens_total)

Total tokens sum across all turns in the loop.
"""
from __future__ import annotations
import json
import time

from anthropic import AsyncAnthropic


DEFAULT_DOMAIN_DESCRIPTION = (
    "static reference documents (potentially older) and more-recent chat/discussion "
    "threads (potentially authoritative updates)"
)


def build_system_prompt(domain_description: str | None = None) -> str:
    """Build a domain-agnostic system prompt. Pass domain_description to specialize."""
    domain = domain_description or DEFAULT_DOMAIN_DESCRIPTION
    return (
        "You answer the user's question using ONLY the corpus available through "
        "your tools. The corpus has two sources: " + domain + ".\n\n"
        "You have four tools:\n"
        "  - list_handbook() / get_handbook(doc_id): the static/reference source\n"
        "  - list_slack() / get_slack(thread_id): the recent/discussion source\n\n"
        "Workflow:\n"
        "  1. Call list_handbook AND list_slack first to see titles and timestamps.\n"
        "  2. Fetch 1-3 relevant items per source via get_* calls.\n"
        "  3. Answer. Prefer the recent source when timestamps indicate the static one is outdated.\n"
        "  4. Cite source titles in square brackets. Be concise: 1-3 sentences.\n\n"
        "Do NOT refuse based on domain assumptions — if the tools contain relevant material, "
        "use it regardless of what the topic sounds like."
    )


# Backwards-compat alias (was hardcoded HR before; default is now domain-agnostic)
SYSTEM_PROMPT = build_system_prompt()


TOOLS = [
    {
        "name": "list_handbook",
        "description": "List all static/reference documents in the corpus (id, title, timestamp). No args.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_handbook",
        "description": "Fetch the full text of a static/reference document by id.",
        "input_schema": {
            "type": "object",
            "properties": {"doc_id": {"type": "string", "description": "doc id from list_handbook"}},
            "required": ["doc_id"],
        },
    },
    {
        "name": "list_slack",
        "description": "List all recent discussion threads (id, title, timestamp, channel, user).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_slack",
        "description": "Fetch the full text of a discussion thread by id.",
        "input_schema": {
            "type": "object",
            "properties": {"thread_id": {"type": "string", "description": "thread id from list_slack"}},
            "required": ["thread_id"],
        },
    },
]


def _list_payload(docs: list[dict], want_type: str) -> list[dict]:
    out = []
    for d in docs:
        if d["type"] != want_type:
            continue
        meta = d["metadata"]
        entry = {"id": d["id"], "title": meta.get("title", d["id"]), "timestamp": meta.get("timestamp", "")}
        if want_type == "slack":
            entry["channel"] = meta.get("channel_name") or meta.get("channel_id") or ""
            entry["user"] = meta.get("user_name") or meta.get("user_id") or ""
            entry["relationship"] = meta.get("relationship", "")
        out.append(entry)
    return out


def _by_id(docs: list[dict]) -> dict:
    return {d["id"]: d for d in docs}


def _execute_tool(name: str, args: dict, docs: list[dict]) -> str:
    try:
        if name == "list_handbook":
            return json.dumps(_list_payload(docs, "static"))
        if name == "get_handbook":
            d = _by_id(docs).get(args.get("doc_id", ""))
            if not d or d["type"] != "static":
                return json.dumps({"error": "unknown doc_id"})
            return d["content"][:6000]
        if name == "list_slack":
            return json.dumps(_list_payload(docs, "slack"))
        if name == "get_slack":
            d = _by_id(docs).get(args.get("thread_id", ""))
            if not d or d["type"] != "slack":
                return json.dumps({"error": "unknown thread_id"})
            return d["content"][:4000]
        return json.dumps({"error": f"unknown tool {name}"})
    except Exception as e:
        return json.dumps({"error": f"tool-exec: {e}"})


async def agent_managed_runner(
    client: AsyncAnthropic,
    question: str,
    docs: list[dict],
    model: str,
    max_iter: int = 6,
    max_tokens: int = 1024,
    domain_description: str | None = None,
) -> tuple[str, float, int, int]:
    """Run the agent-managed tool-use loop. Returns same shape as answer_question_async.

    domain_description: optional one-line corpus description. If None, uses a
    neutral default ('static reference docs + recent chat threads'). Pass a
    specific description when the domain matters (e.g., 'GitLab HR policy docs
    and People-Ops Slack threads'). Prior finding: hardcoding 'HR assistant'
    here caused agent_managed to refuse q-polars-009 as 'not GitLab HR' (0.20).
    """
    system_prompt = build_system_prompt(domain_description)
    t0 = time.time()
    messages: list[dict] = [{"role": "user", "content": question}]
    in_tok_total = 0
    out_tok_total = 0
    final_text = ""

    for _ in range(max_iter):
        resp = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0.0,
            system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
            tools=TOOLS,
            messages=messages,
        )
        u = resp.usage
        in_tok_total += u.input_tokens
        out_tok_total += u.output_tokens

        # Capture any text blocks in this turn
        turn_text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        if turn_text:
            final_text = turn_text  # last-seen text wins

        if resp.stop_reason != "tool_use":
            break

        # Append assistant turn verbatim
        messages.append({"role": "assistant", "content": resp.content})

        tool_results = []
        for block in resp.content:
            if getattr(block, "type", "") == "tool_use":
                result = _execute_tool(block.name, block.input or {}, docs)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
        if not tool_results:
            break
        messages.append({"role": "user", "content": tool_results})
    else:
        final_text = final_text or "(agent hit max iterations without producing a final answer)"

    latency = time.time() - t0
    return final_text, latency, in_tok_total, out_tok_total
