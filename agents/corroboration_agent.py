"""Corroboration agent: deterministic comparison of the two readings, then the verdict.

No LLM here. The comparison is pure code (`core.corroboration`), so the confidence
verdict is as reproducible and testable as the score itself. On EXCLUDED the final
verdict abstains: score is None and the reason says exactly which rule flipped and what
each reading saw. An abstention that names its evidence beats a number that hides a
contradiction.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types

from agents.state_utils import as_plain_dict
from core.corroboration import EXCLUDED, corroborate


class CorroborationAgent(BaseAgent):
    """Reads both readings + the score, writes `corroboration` and the final `verdict`."""

    primary_key: str = "enriched_lead"
    rederived_key: str = "rederived_lead"
    score_key: str = "score_result"
    output_key: str = "verdict"

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        primary = as_plain_dict(ctx.session.state.get(self.primary_key))
        rederived = as_plain_dict(ctx.session.state.get(self.rederived_key))
        score = as_plain_dict(ctx.session.state.get(self.score_key))
        if not primary or not rederived or not score:
            raise RuntimeError(
                "corroboration needs enriched_lead, rederived_lead and score_result in "
                f"state; missing: {[k for k, v in [(self.primary_key, primary), (self.rederived_key, rederived), (self.score_key, score)] if not v]}"
            )

        result = corroborate(primary, rederived)

        if result.verdict == EXCLUDED:
            verdict = {
                "status": EXCLUDED,
                "score": None,  # abstain: no number built on a contradiction
                "reason": result.summary(),
            }
        else:
            verdict = {
                "status": result.verdict,
                "score": score["score"],
                "reason": score["reason"],
            }
        verdict["corroboration"] = asdict(result)

        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=types.Content(
                role="model",
                parts=[types.Part(text=f"[{verdict['status']}] {verdict['reason']}")],
            ),
            actions=EventActions(
                state_delta={
                    "corroboration": asdict(result),
                    self.output_key: verdict,
                }
            ),
        )
