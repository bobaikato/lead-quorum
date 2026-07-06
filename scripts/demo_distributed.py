"""Reproducible proof that the distributed A2A pipeline runs end to end, locally.

Starts the two reader specialists as independent A2A services (different models), then runs
the orchestrator against them over the network and prints the verdict. This is the same
topology deployed on Cloud Run, shrunk to localhost.

    python scripts/demo_distributed.py

Requires GOOGLE_API_KEY in .env.
"""

from __future__ import annotations

import asyncio
import threading
import time

import httpx
import uvicorn
from dotenv import load_dotenv

load_dotenv()

from agents.a2a_server import build_app  # noqa: E402
from agents.distributed import build_distributed_pipeline  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.genai import types  # noqa: E402

CLEAR = (
    "Acme Corp, industrial supplier. About 30 employees. They renewed their contract last "
    "year. Main contact is the VP of Operations. Spends around $6,000 per month."
)
AMBIGUOUS = (
    "TechCo. Maybe seven or eight thousand a month, hard to say. Around 25 people give or "
    "take. Talked to someone there once. They mentioned possibly renewing."
)


def _serve(agent: str, port: int) -> uvicorn.Server:
    server = uvicorn.Server(
        uvicorn.Config(
            build_app(agent, host="127.0.0.1", port=port),
            host="127.0.0.1",
            port=port,
            log_level="error",
        )
    )
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(80):
        try:
            if (
                httpx.get(
                    f"http://127.0.0.1:{port}/.well-known/agent-card.json", timeout=1
                ).status_code
                == 200
            ):
                return server
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.25)
    raise RuntimeError(f"{agent} on {port} never came up")


async def _run(pipeline, notes: str) -> dict:
    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name="demo", user_id="u")
    runner = Runner(app_name="demo", agent=pipeline, session_service=session_service)
    async for _event in runner.run_async(
        user_id="u",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=notes)]),
    ):
        pass
    return (
        await session_service.get_session(app_name="demo", user_id="u", session_id=session.id)
    ).state


def main() -> None:
    s1 = _serve("enrichment", 8771)
    s2 = _serve("rederive", 8772)
    print("two A2A services up: enrichment:8771, rederive:8772\n")
    pipeline = build_distributed_pipeline(
        "http://127.0.0.1:8771/.well-known/agent-card.json",
        "http://127.0.0.1:8772/.well-known/agent-card.json",
    )
    for label, notes in [("CLEAR lead", CLEAR), ("AMBIGUOUS lead", AMBIGUOUS)]:
        state = asyncio.run(_run(pipeline, notes))
        verdict = state["verdict"]
        print(f"{label}: {verdict['status']}  score={verdict['score']}")
        print(f"  {verdict['reason']}\n")
    s1.should_exit = True
    s2.should_exit = True


if __name__ == "__main__":
    main()
