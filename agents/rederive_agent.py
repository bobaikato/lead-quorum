"""Re-derivation agent: an independent second reading of the same raw notes.

Same schema as the enrichment agent, different posture: this one is framed as an auditor
that extracts strictly and independently. Its output is never scored directly; it exists
so the corroboration step can compare two readings that do not share a prompt, and refuse
to trust a score the two readings disagree about.

Honest limitation, also documented in the README: both readings come from the same model
family, so this catches extraction variance and ambiguous-input disagreements, not
systematic model bias. Swapping this agent to a different model (or a remote A2A service
run by someone else) strengthens the guarantee without touching the pipeline, which is
exactly why it is a separate agent.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.genai import types

from agents.config import REDERIVE_MODEL
from core.schemas import EnrichedLead

# Same extraction rules as the enrichment agent on purpose: the independence must come
# from running a different model, not from one reader applying stricter rules than the
# other. If the two disagree, it should mean the notes are genuinely ambiguous, not that
# we rigged one reader to be pedantic.
INSTRUCTION = """You are an independent verification reader. The user message contains raw
notes about one company. Read the notes yourself and extract the structured fields from
scratch, independently.

Rules:
- Extract values the notes state, including clear approximations ("about 30" -> 30,
  "around 8k a month" -> 8000). If a signal is genuinely not stated, or too vague to pin
  to a value, leave it at its default (0 for numbers, empty string for text, false for
  renewed). Do not guess beyond what the notes support.
- monthly_spend is USD per month. seats is the team size.
- contact_role is a lowercase role such as owner, vp, director, c-level, or analyst.
- renewed is true only if the notes indicate a renewal or an existing/returning customer.
Return only the structured fields."""


def build_rederive_agent() -> LlmAgent:
    """Fresh instance per pipeline (ADK agents hold a single parent)."""
    return LlmAgent(
        name="rederive_agent",
        model=REDERIVE_MODEL,
        description="Independently re-extracts the lead fields for corroboration.",
        instruction=INSTRUCTION,
        output_schema=EnrichedLead,
        output_key="rederived_lead",
        # temperature 0: this reader disagrees with enrichment only when the notes are
        # genuinely ambiguous (strict vs generous posture), never from sampling noise.
        generate_content_config=types.GenerateContentConfig(temperature=0.0),
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )
