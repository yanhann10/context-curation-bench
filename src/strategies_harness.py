"""Thin → Medium → Thick harness axis (Project 9).

Holds the curation strategy fixed (tool-use over the same 4 tools from
strategies_agent_managed) and varies only the *harness* — the orchestration
logic around the model call. Tests the "simpler is better" claim directly.

- thin_harness:   bare 2-turn loop, no preamble, 2 tools (get_* only after model guesses id)
- medium_harness: current agent_managed (4 tools, max 6 turns, corpus-split preamble)  [reuse]
- thick_harness:  3 phases — PLAN (JSON sketch of sub-questions + likely sources)
                  → EXECUTE (tool-use with plan injected) → VERIFY (re-check answer vs
                  fetched evidence; one optional extra execute pass if unverified claims)

All three return (answer, latency_s, in_tokens, out_tokens) summed across every
call in the loop, so cost/latency reflect full harness overhead.
"""
from __future__ import annotations
import json
import time

from anthropic import AsyncAnthropic

from .llm_client import complete_text, complete_json
from .strategies_agent_managed import (
    TOOLS as AGENT_TOOLS,
    _execute_tool,
)


# ---------------- THIN HARNESS ----------------

THIN_SYSTEM = (
    "You have four tools: list_handbook, get_handbook(doc_id), list_slack, "
    "get_slack(thread_id). Fetch what you need from the corpus, then answer "
    "in 1-3 sentences. Use the tools regardless of what the question topic "
    "sounds like — the corpus may cover it."
)


async def thin_harness_runner(
    client: AsyncAnthropic,
    question: str,
    docs: list[dict],
    model: str,
    max_iter: int = 3,
    max_tokens: int = 1024,
    domain_description: str | None = None,
) -> tuple[str, float, int, int]:
    """Minimal harness: short system prompt, low max_iter cap, no role guidance.

    domain_description: optional one-line corpus hint; appended to THIN_SYSTEM
    if provided. Leave None for domain-agnostic behaviour (recommended default
    after the Polars run found domain-locked prompts refuse off-topic questions).
    """
    system_text = THIN_SYSTEM
    if domain_description:
        system_text = system_text + f"\n\nCorpus: {domain_description}."
    t0 = time.time()
    messages: list[dict] = [{"role": "user", "content": question}]
    in_tot = out_tot = 0
    final_text = ""

    for _ in range(max_iter):
        resp = await client.messages.create(
            model=model, max_tokens=max_tokens, temperature=0.0,
            system=[{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}],
            tools=AGENT_TOOLS,
            messages=messages,
        )
        u = resp.usage
        in_tot += u.input_tokens
        out_tot += u.output_tokens
        turn_text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        if turn_text:
            final_text = turn_text
        if resp.stop_reason != "tool_use":
            break
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
    return final_text or "(thin harness hit max iterations)", time.time() - t0, in_tot, out_tot


# ---------------- THICK HARNESS ----------------

PLAN_SYSTEM = (
    "You are a planning step for a tool-using agent. The corpus has two sources: "
    "a static/reference set (list_handbook / get_handbook) and a recent discussion "
    "set (list_slack / get_slack). Given a user question, output a JSON plan. "
    "Do not fetch anything yet. Shape: "
    '{"sub_questions": ["<concrete sub-question 1>", ...], '
    '"likely_handbook_topics": ["<topic>", ...], '
    '"likely_slack_topics": ["<topic>", ...], '
    '"risks": ["<what could go wrong, e.g. stale source, ambiguous question>"], '
    '"specific_facts_needed": ["<concrete fact or API name or figure the answer must contain>"]}'
)

EXECUTE_SYSTEM = (
    "You are executing a plan to answer a question. Tools: list_handbook, "
    "get_handbook(doc_id), list_slack, get_slack(thread_id). "
    "The static source (handbook) may be older; the discussion source (slack) may be "
    "more recent — prefer the recent one when timestamps indicate the static source is outdated. "
    "Follow the plan but adapt if the plan proves wrong. Cite source titles. "
    "Use the tools regardless of what the topic sounds like — the corpus may cover it."
)

VERIFY_SYSTEM = (
    "You just produced an answer based on fetched evidence. Check two things:\n"
    "  1. UNVERIFIED CLAIMS — statements in the answer that are not directly supported "
    "     by text you fetched.\n"
    "  2. MISSING CLAIMS — specific_facts_needed (from the plan, if available) or "
    "     concrete API names, dollar figures, day-counts, policy names that the golden "
    "     answer would surface and that the user is likely to need — which the answer "
    "     OMITS even though the fetched evidence contains them.\n\n"
    "Output JSON: "
    '{"unverified_claims": ["<claim>", ...], '
    '"missing_claims": ["<fact the answer should mention but doesn\'t>", ...], '
    '"needs_more_fetch": <bool>, "suggested_sources": ["<doc id or thread id>", ...]}. '
    "Set needs_more_fetch=true if either list is non-empty AND fetching more evidence "
    "would plausibly help."
)

REFINE_SYSTEM = (
    "You have an initial answer plus follow-up evidence. Produce a final answer "
    "that fully addresses the question, uses the most recent source on disagreement, "
    "and cites source titles. 1-3 sentences."
)


async def _execute_loop(
    client: AsyncAnthropic, question: str, plan_text: str,
    docs: list[dict], model: str, max_iter: int, max_tokens: int,
) -> tuple[str, int, int, list[dict]]:
    """Tool-use loop seeded with a plan. Returns (answer, in_tok, out_tok, transcript)."""
    in_tot = out_tot = 0
    messages: list[dict] = [{
        "role": "user",
        "content": f"PLAN:\n{plan_text}\n\nQUESTION:\n{question}\n\nFetch what the plan suggests and answer.",
    }]
    final_text = ""
    for _ in range(max_iter):
        resp = await client.messages.create(
            model=model, max_tokens=max_tokens, temperature=0.0,
            system=[{"type": "text", "text": EXECUTE_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            tools=AGENT_TOOLS,
            messages=messages,
        )
        in_tot += resp.usage.input_tokens
        out_tot += resp.usage.output_tokens
        turn_text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        if turn_text:
            final_text = turn_text
        if resp.stop_reason != "tool_use":
            break
        messages.append({"role": "assistant", "content": resp.content})
        tool_results = []
        for block in resp.content:
            if getattr(block, "type", "") == "tool_use":
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": _execute_tool(block.name, block.input or {}, docs),
                })
        if not tool_results:
            break
        messages.append({"role": "user", "content": tool_results})
    return final_text, in_tot, out_tot, messages


async def thick_harness_runner(
    client: AsyncAnthropic,
    question: str,
    docs: list[dict],
    model: str,
    max_iter: int = 5,
    max_tokens: int = 1024,
    verifier_model: str | None = None,
    domain_description: str | None = None,
) -> tuple[str, float, int, int]:
    """3-phase harness: plan -> execute -> verify (+ optional refine with new evidence).

    verifier_model: if set (and different from `model`), the verify phase uses this
    second model instead of the same model that produced the answer. This
    mitigates the self-confidence blind spot observed on HR q-v2-010 and
    Polars q-polars-007 — a single-model verifier pattern-matches surface
    features without re-checking sources.
    domain_description: optional corpus hint forwarded to plan/execute/verify prompts.
    """
    verify_model = verifier_model or model
    domain_hint = f"\n\nCorpus domain: {domain_description}" if domain_description else ""
    t0 = time.time()
    in_tot = out_tot = 0

    # Phase 1: plan
    plan_data, p_in, p_out, _ = await complete_json(
        client, user=f"QUESTION:\n{question}" + domain_hint,
        system=PLAN_SYSTEM, model=model, max_tokens=400,
    )
    in_tot += p_in; out_tot += p_out
    plan_text = json.dumps(plan_data, indent=2) if plan_data else "(empty plan)"

    # Phase 2: execute
    answer, e_in, e_out, transcript = await _execute_loop(
        client, question, plan_text, docs, model, max_iter=max_iter, max_tokens=max_tokens,
    )
    in_tot += e_in; out_tot += e_out

    # Phase 3: verify (may use a different model — cross-model verifier reduces self-confidence bias)
    plan_specific_facts = ""
    if isinstance(plan_data, dict) and plan_data.get("specific_facts_needed"):
        plan_specific_facts = (
            "\n\nPLAN'S specific_facts_needed (check whether the answer surfaces each):\n"
            + "\n".join(f"- {f}" for f in plan_data["specific_facts_needed"])
        )
    verify_payload = (
        f"QUESTION: {question}\n\nANSWER: {answer[:1500]}" + plan_specific_facts
        + "\n\nCheck for unverified claims AND missing claims (facts the answer should surface)."
    )
    v_data, v_in, v_out, _ = await complete_json(
        client, user=verify_payload, system=VERIFY_SYSTEM,
        model=verify_model, max_tokens=320,
    )
    in_tot += v_in; out_tot += v_out
    needs_more = bool(v_data.get("needs_more_fetch", False)) if isinstance(v_data, dict) else False

    if needs_more:
        # Optional refine: one extra execute pass with the verify feedback injected
        feedback = json.dumps(v_data, indent=2)
        refined_prompt = (
            f"PRIOR ANSWER:\n{answer}\n\n"
            f"VERIFIER FEEDBACK:\n{feedback}\n\n"
            f"ORIGINAL QUESTION:\n{question}\n\n"
            "Fetch what's needed to support the unverified claims, then give a final answer."
        )
        refine_answer, r_in, r_out, _ = await _execute_loop(
            client, refined_prompt, plan_text, docs, model,
            max_iter=max(2, max_iter // 2), max_tokens=max_tokens,
        )
        in_tot += r_in; out_tot += r_out
        if refine_answer:
            # One final polishing pass to produce a clean final answer
            final_text, f_in, f_out, _ = await complete_text(
                client,
                user=f"QUESTION: {question}\n\nDRAFT: {refine_answer[:1500]}\n\nProduce the final answer.",
                system=REFINE_SYSTEM, model=model, max_tokens=400,
            )
            in_tot += f_in; out_tot += f_out
            if final_text.strip():
                answer = final_text

    return answer, time.time() - t0, in_tot, out_tot
