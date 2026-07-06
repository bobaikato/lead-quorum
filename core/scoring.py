"""Deterministic lead scoring with an audit trail welded to the number.

The model proposes signals (upstream, in the enrichment agent); this module disposes the
score. There is no LLM here on purpose: a score someone acts on has to be reproducible and
defensible row by row, so the number is pure code.

The one rule that matters: every point is granted AND explained in the same place, so the
reason can never drift from the score. `ScoreResult.reconciles()` proves it, and the test
suite fails CI if it ever stops being true.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Rule:
    """One scoring rule. It owns BOTH the points and the words for them, so the two can
    never be edited in different files and fall out of sync. `fires` decides whether the
    rule applies to a lead; `because` builds the human reason at the instant it fires."""

    name: str
    points: int
    fires: Callable[[dict], bool]
    because: Callable[[dict], str]
    field: str = ""  # the lead field this rule reads; used by corroboration deltas


@dataclass(frozen=True)
class ScorePart:
    """A single rule that fired: the points it granted and the reason it granted them.
    Emitted together, so they cannot diverge."""

    points: int
    reason: str


@dataclass(frozen=True)
class ScoreResult:
    score: int                      # final, after the cap
    raw: int                        # pre-cap sum, kept so the cap is never a silent lie
    cap: int
    parts: tuple[ScorePart, ...]
    reason: str

    def reconciles(self) -> bool:
        """The points named in the parts must sum to the pre-cap score. If this is ever
        False, the audit trail has started lying and the result is not trustworthy."""
        return sum(p.points for p in self.parts) == self.raw


# The rubric is data, not branches buried in a function. Weights are designed to top out
# exactly at the cap, so `min` never silently absorbs anything under normal inputs; if a
# future edit makes them overshoot, the cap is named in the reason instead of hidden.
RUBRIC: tuple[Rule, ...] = (
    Rule(
        name="budget",
        points=40,
        fires=lambda lead: lead.get("monthly_spend", 0) >= 8000,
        because=lambda lead: f"+40 monthly spend {lead['monthly_spend']} >= 8000",
        field="monthly_spend",
    ),
    Rule(
        name="team_size",
        points=35,
        fires=lambda lead: lead.get("seats", 0) >= 25,
        because=lambda lead: f"+35 team of {lead['seats']} seats >= 25",
        field="seats",
    ),
    Rule(
        name="decision_maker",
        points=15,
        fires=lambda lead: lead.get("contact_role") in {"owner", "vp", "director", "c-level"},
        because=lambda lead: f"+15 reachable decision maker ({lead['contact_role']})",
        field="contact_role",
    ),
    Rule(
        name="prior_relationship",
        points=10,
        fires=lambda lead: bool(lead.get("renewed")),
        because=lambda lead: "+10 renewed at least once",
        field="renewed",
    ),
)

CAP = 100


def score_lead(lead: dict, rubric: tuple[Rule, ...] = RUBRIC, cap: int = CAP) -> ScoreResult:
    """Score one enriched lead. Returns the number, the reason built from the same rules
    that produced the number, and enough structure to reconcile the two.

    The reason only ever names signals that actually fired. A rule that does not fire
    contributes no points and no words, so the explanation can never claim a signal the
    score did not use. That is the whole point of "why is this a 60 and not a 40": the
    answer is sitting in the reason, and it adds up.
    """
    parts: list[ScorePart] = []
    for rule in rubric:
        if rule.fires(lead):
            parts.append(ScorePart(points=rule.points, reason=rule.because(lead)))

    raw = sum(part.points for part in parts)
    score = min(raw, cap)

    body = "; ".join(part.reason for part in parts) if parts else "no signals fired"
    capped_note = "" if raw <= cap else f" (capped from {raw})"
    reason = f"{score}/{cap}{capped_note}: {body}"

    return ScoreResult(score=score, raw=raw, cap=cap, parts=tuple(parts), reason=reason)
