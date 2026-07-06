"""The full lead-qualifier pipeline.

Topology (see DESIGN.md):

    SequentialAgent
      1. ParallelAgent            <- the efficiency win: the two independent readings of
           enrichment_agent          the raw notes run CONCURRENTLY, so wall-clock is one
           rederive_agent            LLM round-trip, not two
      2. ScoringAgent             <- deterministic: the number + a reason that reconciles
      3. CorroborationAgent       <- deterministic: compare readings in score-space,
                                     verdict CONFIRMED / REVIEW / EXCLUDED (abstain)

Model proposes (step 1), code disposes (steps 2-3). Exactly two LLM calls per lead, both
in parallel; everything after them is pure, tested Python.
"""

from __future__ import annotations

from google.adk.agents import ParallelAgent, SequentialAgent

from agents.corroboration_agent import CorroborationAgent
from agents.enrichment_agent import build_enrichment_agent
from agents.rederive_agent import build_rederive_agent
from agents.scoring_agent import ScoringAgent


def build_lead_pipeline() -> SequentialAgent:
    return SequentialAgent(
        name="lead_qualifier_pipeline",
        sub_agents=[
            ParallelAgent(
                name="independent_readers",
                sub_agents=[build_enrichment_agent(), build_rederive_agent()],
            ),
            ScoringAgent(name="scoring_agent"),
            CorroborationAgent(name="corroboration_agent"),
        ],
    )


# The `adk` CLI looks for a module-level `root_agent`.
root_agent = build_lead_pipeline()
