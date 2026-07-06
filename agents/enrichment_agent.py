"""Enrichment agent: an LlmAgent that turns raw lead notes into a structured EnrichedLead.

This is the "model proposes" half of the system. It normalizes messy input into the exact
fields the deterministic scorer reads, and is instructed to leave a signal absent
(0 / empty / False) rather than invent it, so the scorer never rewards a hallucinated
number. The corroborator downstream re-checks these fields independently.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.genai import types

from agents.config import MODEL
from core.schemas import EnrichedLead

INSTRUCTION = """You are a B2B lead enrichment agent.
The user message contains raw notes about one company (free text and/or partial fields).
Extract a structured lead from it.

Rules:
- Only assert a value you can justify from the notes. If a signal is not stated, leave it
  at its default (0 for numbers, empty string for text, false for renewed). Do NOT guess.
- monthly_spend is USD per month. seats is the team size.
- contact_role is a lowercase role such as owner, vp, director, c-level, or analyst.
- renewed is true only if the notes indicate they renewed or are an existing/returning
  customer.
Return only the structured fields."""

def build_enrichment_agent() -> LlmAgent:
    """Return a fresh enrichment agent.

    ADK agents can hold only one parent, so a single module-level instance cannot be
    reused across pipelines (or across a pipeline and a standalone A2A service). Build a
    new one per use.
    """
    return LlmAgent(
        name="enrichment_agent",
        model=MODEL,
        description="Normalizes raw lead notes into structured, scoring-ready fields.",
        instruction=INSTRUCTION,
        output_schema=EnrichedLead,
        output_key="enriched_lead",
        # temperature 0 so disagreement with the auditor signals real ambiguity in the
        # notes, not sampling noise between two identical-model readers.
        generate_content_config=types.GenerateContentConfig(temperature=0.0),
        # output_schema is a leaf capability: no tools, no transfer to other agents.
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )
