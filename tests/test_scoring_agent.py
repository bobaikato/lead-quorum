"""Integration test: the Scoring agent driven through the real ADK Runner.

No LLM and no credentials are needed because the agent is deterministic. This proves the
agent wires into ADK correctly: it reads the enriched lead from session state, and the
runner persists its structured result back to state under `score_result`.
"""

import asyncio

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agents.scoring_agent import ScoringAgent

APP = "lead_qualifier_test"
USER = "u1"


def run_scoring(enriched_lead: dict) -> dict:
    """Run the ScoringAgent once over an enriched lead, return the final session state."""

    async def _run():
        session_service = InMemorySessionService()
        session = await session_service.create_session(
            app_name=APP, user_id=USER, state={"enriched_lead": enriched_lead}
        )
        runner = Runner(
            app_name=APP,
            agent=ScoringAgent(name="scoring_agent"),
            session_service=session_service,
        )
        async for _event in runner.run_async(
            user_id=USER,
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text="score")]),
        ):
            pass
        final = await session_service.get_session(
            app_name=APP, user_id=USER, session_id=session.id
        )
        return final.state

    return asyncio.run(_run())


def test_agent_writes_reconciling_result_to_state():
    state = run_scoring(
        {"monthly_spend": 6000, "seats": 30, "renewed": True, "contact_role": "vp"}
    )
    result = state["score_result"]
    assert result["score"] == 60
    assert sum(part["points"] for part in result["parts"]) == result["raw"]
    assert "monthly spend" not in result["reason"]  # spend did not fire, so not claimed


def test_agent_empty_lead_is_a_defensible_zero():
    state = run_scoring({})
    result = state["score_result"]
    assert result["score"] == 0
    assert result["raw"] == 0
    assert "no signals fired" in result["reason"]
