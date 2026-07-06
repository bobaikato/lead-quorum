"""One reusable entry point for running the full pipeline over raw lead notes.

Both the web frontend and any CLI/test call this, so there is a single place that knows how
to drive the ADK Runner and unpack the final state into a plain result dict.
"""

from __future__ import annotations

import os

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agents.distributed import build_distributed_pipeline
from agents.pipeline import build_lead_pipeline
from agents.state_utils import as_plain_dict

APP_NAME = "lead_qualifier"


def _build_pipeline():
    """Distributed A2A pipeline when the two service URLs are configured (Cloud Run),
    otherwise the single-process pipeline (local dev). The scoring and corroboration are
    identical either way; only where the two readers run changes."""
    enrichment_url = os.environ.get("ENRICHMENT_CARD_URL")
    rederive_url = os.environ.get("REDERIVE_CARD_URL")
    if enrichment_url and rederive_url:
        return build_distributed_pipeline(enrichment_url, rederive_url)
    return build_lead_pipeline()


async def qualify(notes: str, user_id: str = "web") -> dict:
    """Run enrichment ‖ rederive -> scoring -> corroboration over `notes`.

    Returns the two independent readings, the deterministic score, and the confidence
    verdict, so the caller can show the whole audit trail, not just a number.
    """
    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name=APP_NAME, user_id=user_id)
    runner = Runner(
        app_name=APP_NAME,
        agent=_build_pipeline(),
        session_service=session_service,
    )
    async for _event in runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=notes)]),
    ):
        pass
    state = (
        await session_service.get_session(
            app_name=APP_NAME, user_id=user_id, session_id=session.id
        )
    ).state
    return {
        "enriched": as_plain_dict(state.get("enriched_lead")),
        "rederived": as_plain_dict(state.get("rederived_lead")),
        "score": as_plain_dict(state.get("score_result")),
        "verdict": state.get("verdict"),
    }
