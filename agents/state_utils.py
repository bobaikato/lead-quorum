"""Small helpers for reading structured values out of ADK session state.

Depending on how an upstream agent stored its output, a value can arrive as a pydantic
model, a JSON string, or a plain dict. Downstream deterministic agents normalize before
use so their logic never depends on which producer ran.
"""

from __future__ import annotations

import json


def as_plain_dict(value) -> dict:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):  # a pydantic model
        return value.model_dump()
    if isinstance(value, str):  # stored as a JSON string
        return json.loads(value)
    return dict(value)
