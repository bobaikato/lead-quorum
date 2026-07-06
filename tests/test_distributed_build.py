"""Cheap regression: the distributed pipeline assembles into a valid agent tree.

The full networked round-trip is exercised by scripts/demo_distributed.py (needs live
services + API key); here we just guard that the topology still constructs, so a refactor
that breaks the distributed wiring fails fast without spinning up servers.
"""

from agents.distributed import build_distributed_pipeline


def test_distributed_pipeline_builds():
    pipeline = build_distributed_pipeline(
        "http://svc-a/.well-known/agent-card.json",
        "http://svc-b/.well-known/agent-card.json",
    )
    assert pipeline.name == "distributed_lead_qualifier"
    # sequential: [parallel readers, scoring, corroboration]
    assert len(pipeline.sub_agents) == 3
    readers = pipeline.sub_agents[0]
    assert readers.name == "remote_readers"
    assert len(readers.sub_agents) == 2  # one leg per remote reader
