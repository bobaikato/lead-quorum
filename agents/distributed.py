"""The distributed orchestrator: the two readers are REMOTE A2A services.

This is the Cloud Run topology. Each reader runs as its own service (agents/a2a_server.py);
here the orchestrator reaches them with RemoteA2aAgent and keeps the deterministic scoring
and corroboration in-process. It is the same shape as the local pipeline, with the two LLM
legs swapped for network calls, which is the whole point of A2A: the reliability code does
not change when the readers move onto separate machines.

RemoteA2aAgent has no output_key, so a small CaptureRemoteOutput adapter reads the JSON the
remote returned out of the event log and writes it to state under the key the downstream
deterministic agents already expect. That keeps scoring and corroboration identical to the
local pipeline.
"""

from __future__ import annotations

import json
from typing import AsyncGenerator

from google.adk.agents import BaseAgent, ParallelAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.events import Event, EventActions
from google.genai import types

from agents.corroboration_agent import CorroborationAgent
from agents.scoring_agent import ScoringAgent


class CaptureRemoteOutput(BaseAgent):
    """Pull the latest JSON payload authored by `from_agent` out of the session event log
    and store it in state under `output_key`, normalizing the A2A response into the same
    shape a local agent's output_key would have produced."""

    from_agent: str
    output_key: str

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        payload = None
        for ev in reversed(ctx.session.events):
            if ev.author != self.from_agent or not ev.content or not ev.content.parts:
                continue
            text = "".join(p.text for p in ev.content.parts if getattr(p, "text", None))
            text = text.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
                break
            except json.JSONDecodeError:
                continue
        if payload is None:
            raise RuntimeError(f"no JSON output found from remote agent {self.from_agent!r}")
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            actions=EventActions(state_delta={self.output_key: payload}),
        )


def _remote_leg(agent_name: str, card_url: str, output_key: str) -> SequentialAgent:
    remote = RemoteA2aAgent(
        name=agent_name,
        description=f"remote {agent_name} A2A service",
        agent_card=card_url,
    )
    capture = CaptureRemoteOutput(
        name=f"capture_{output_key}", from_agent=agent_name, output_key=output_key
    )
    return SequentialAgent(name=f"{agent_name}_leg", sub_agents=[remote, capture])


def build_distributed_pipeline(
    enrichment_card_url: str, rederive_card_url: str
) -> SequentialAgent:
    return SequentialAgent(
        name="distributed_lead_qualifier",
        sub_agents=[
            ParallelAgent(
                name="remote_readers",
                sub_agents=[
                    _remote_leg("enrichment_agent", enrichment_card_url, "enriched_lead"),
                    _remote_leg("rederive_agent", rederive_card_url, "rederived_lead"),
                ],
            ),
            ScoringAgent(name="scoring_agent"),
            CorroborationAgent(name="corroboration_agent"),
        ],
    )
