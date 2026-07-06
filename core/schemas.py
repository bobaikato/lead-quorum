"""Typed contracts passed between agents.

Pinning these as pydantic models lets each LlmAgent emit validated structured output
(`output_schema=`) instead of free text, which is what makes the A2A hand-offs contracts
rather than hopeful string parsing.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class EnrichedLead(BaseModel):
    """The scoring-ready view of a lead.

    The enrichment agent fills this from raw notes; `core.scoring` reads exactly these
    fields. Absent signals stay at their default (0 / empty / False) and are never
    guessed, so a missing signal scores as absent instead of inflating the number.
    """

    company: str = Field(description="company name")
    industry: str = Field(default="", description="industry, empty if unknown")
    size_band: str = Field(
        default="", description="one of: smb, mid-market, enterprise; empty if unknown"
    )
    monthly_spend: int = Field(
        default=0, description="estimated monthly spend in USD, 0 if not stated"
    )
    seats: int = Field(default=0, description="team size / seats, 0 if not stated")
    contact_role: str = Field(
        default="",
        description="role of the known contact (owner, vp, director, c-level, analyst, ...), empty if unknown",
    )
    renewed: bool = Field(
        default=False,
        description="true only if the notes say they renewed or are a returning customer",
    )
    tech_signals: list[str] = Field(
        default_factory=list, description="notable tools or tech mentioned"
    )
