"""Serve one specialist as an A2A HTTPS service.

Each specialist is meant to run as its own container (its own Cloud Run service). This is
the entrypoint they share: pick the agent by name (AGENT env var) and expose it over A2A
with `to_a2a`, which returns a Starlette app served by uvicorn. The orchestrator then
reaches each one as a remote A2A agent, which is what makes the system distributed rather
than one process pretending to be several.

Run locally:   AGENT=enrichment uvicorn agents.a2a_server:app --port 8080
On Cloud Run:   one service per AGENT value, PORT injected by the platform.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from google.adk.a2a.utils.agent_to_a2a import to_a2a

from agents.enrichment_agent import build_enrichment_agent
from agents.rederive_agent import build_rederive_agent

# Only the LLM specialists are exposed over A2A. Scoring and corroboration are
# deterministic and cheap, so they stay in the orchestrator process rather than paying a
# network hop to run a few lines of pure Python.
BUILDERS = {
    "enrichment": build_enrichment_agent,
    "rederive": build_rederive_agent,
}


def build_app(agent_name: str | None = None, host: str = "0.0.0.0", port: int = 8080):
    name = agent_name or os.environ.get("AGENT", "enrichment")
    if name not in BUILDERS:
        raise SystemExit(f"unknown AGENT {name!r}; choose one of {sorted(BUILDERS)}")
    # The agent card must advertise a reachable address. Locally that is host:port; on
    # Cloud Run the container binds to $PORT but is reached at the public HTTPS URL, so set
    # PUBLIC_URL to the service URL and the card will point clients at the right place.
    public = os.environ.get("PUBLIC_URL")
    if public:
        u = urlparse(public)
        protocol = u.scheme or "https"
        return to_a2a(
            BUILDERS[name](),
            host=u.hostname or host,
            port=u.port or (443 if protocol == "https" else 80),
            protocol=protocol,
        )
    return to_a2a(BUILDERS[name](), host=host, port=port)


# For `uvicorn agents.a2a_server:app`
app = build_app(port=int(os.environ.get("PORT", "8080")))
