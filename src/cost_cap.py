"""Cost-cap safety net — abort a run if accumulated cost crosses a threshold.

Wrap any AsyncAnthropic / AsyncAnthropicBedrock client with CostCappedClient to
enforce a dollar ceiling across all messages.create() calls. Raises CostBudgetExceeded
when the next call's projected cost would exceed the cap — the partial results
written to disk by run_strategy_async checkpoints are preserved.
"""
from __future__ import annotations
import threading
from typing import Any

from .llm_client import cost_usd as _cost_usd


class CostBudgetExceeded(RuntimeError):
    pass


class CostTracker:
    def __init__(self, cap_usd: float):
        self.cap_usd = cap_usd
        self.spent_usd = 0.0
        self._lock = threading.Lock()

    def charge(self, model: str, in_tok: int, out_tok: int) -> None:
        c = _cost_usd(model, in_tok, out_tok)
        with self._lock:
            self.spent_usd += c
            if self.spent_usd > self.cap_usd:
                raise CostBudgetExceeded(
                    f"cost cap exceeded: spent=${self.spent_usd:.3f} cap=${self.cap_usd:.3f}"
                )

    def report(self) -> str:
        return f"${self.spent_usd:.3f} / ${self.cap_usd:.3f}"


def wrap_messages_create(client: Any, tracker: CostTracker) -> None:
    """Monkey-patch client.messages.create to charge the tracker on each response.

    Safe because the Anthropic SDK's messages.create returns a Message whose .usage
    has input_tokens + output_tokens. We read model from the kwargs.
    """
    original = client.messages.create

    async def wrapped(**kwargs):
        resp = await original(**kwargs)
        try:
            model = kwargs.get("model", "")
            u = getattr(resp, "usage", None)
            if u is not None:
                tracker.charge(model, u.input_tokens, u.output_tokens)
        except CostBudgetExceeded:
            raise
        except Exception:
            # If we can't read usage for any reason, don't crash the whole run.
            pass
        return resp

    client.messages.create = wrapped  # type: ignore[attr-defined]
