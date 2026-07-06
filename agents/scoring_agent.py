"""ADK Scoring agent: a deterministic BaseAgent wrapping the pure scoring core.

There is no LLM in this agent on purpose. The number is set by code, never by a model.
The agent reads the enriched lead from session state, scores it with `core.scoring`,
refuses to emit a result whose reason does not reconcile to its score, and writes the
result back to state under `output_key` for the corroborator and orchestrator to read.

This is the "code disposes" half of the system: the LLM agents upstream propose signals,
this step turns them into a defensible, auditable number.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types

from agents.state_utils import as_plain_dict
from core.scoring import score_lead


class ScoringAgent(BaseAgent):
    """Deterministic scoring step.

    Reads the enriched lead from `state[input_key]`, writes the scored result (score,
    reason, parts, confidence surface) to `state[output_key]`. Emits the reason as the
    event text so it is visible in a trace, but the authoritative artifact is the
    structured result in state.
    """

    input_key: str = "enriched_lead"
    output_key: str = "score_result"

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        lead = as_plain_dict(ctx.session.state.get(self.input_key))
        result = score_lead(lead)

        if not result.reconciles():
            # The audit trail must never leave this agent lying. If the points named in
            # the reason ever stop summing to the score, fail loud instead of emitting a
            # confident, wrong number downstream.
            raise RuntimeError(
                f"scoring reason does not reconcile to score: {result.reason!r}"
            )

        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=types.Content(
                role="model", parts=[types.Part(text=result.reason)]
            ),
            actions=EventActions(state_delta={self.output_key: asdict(result)}),
        )
