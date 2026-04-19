"""LLM-judge grader. Reuses src.evaluator_async.judge_async."""
from __future__ import annotations

from .registry import grader
from src.evaluator_async import judge_async


@grader("llm_judge")
async def llm_judge(ctx, question, answer: str) -> dict:
    client = ctx["client"]
    model = ctx.get("judge_model", "claude-opus-4-7")
    quality, note, j_in, j_out = await judge_async(
        client, question.as_legacy_dict(), answer, model,
    )
    return {
        "quality": quality,
        "note": note,
        "judge_prompt_tokens": j_in,
        "judge_completion_tokens": j_out,
    }
