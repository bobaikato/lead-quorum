"""Corroboration: compare two independent readings of one lead, in score-space.

The comparison is deliberately done in SCORE-space, not value-space. What matters is not
whether two extractions produced byte-identical fields; it is whether they disagree about
which scoring rules fire. Two readings a few hundred dollars apart on the same side of a
threshold yield the same score: that is drift worth flagging, not a contradiction. Two
readings on opposite sides of a threshold yield different scores: no single number built
on that disagreement deserves trust, so the verdict is EXCLUDED and the honest output is
abstention, carrying both values and which rule flipped.

A defensible EXCLUDED beats a fake-precise number built on a contradiction.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.scoring import RUBRIC, Rule

CONFIRMED = "CONFIRMED"
REVIEW = "REVIEW"
EXCLUDED = "EXCLUDED"

# Fields compared for drift when the fired-rule sets agree.
_NUMERIC_FIELDS = ("monthly_spend", "seats")
_CATEGORICAL_FIELDS = ("contact_role", "renewed")
_REL_TOLERANCE = 0.15  # numeric readings within 15% of each other count as agreeing


@dataclass(frozen=True)
class Delta:
    """One disagreement between the two readings."""

    field: str
    primary: object
    rederived: object
    effect: str  # "rule_flipped" (score-material) | "value_drift" (score-neutral)


@dataclass(frozen=True)
class Corroboration:
    verdict: str  # CONFIRMED | REVIEW | EXCLUDED
    deltas: tuple[Delta, ...]
    fired_primary: tuple[str, ...]
    fired_rederived: tuple[str, ...]

    def summary(self) -> str:
        if self.verdict == CONFIRMED:
            return "CONFIRMED: independent re-extraction agrees on every scoring signal"
        detail = "; ".join(
            f"{d.field}: {d.primary!r} vs {d.rederived!r}" for d in self.deltas
        )
        if self.verdict == REVIEW:
            return f"REVIEW: same signals fire but readings drift ({detail})"
        return (
            f"EXCLUDED: readings disagree on which signals fire ({detail}); "
            "abstaining instead of scoring a contradiction"
        )


def _numbers_close(a: float, b: float) -> bool:
    if not a and not b:
        return True
    return abs(a - b) <= _REL_TOLERANCE * max(abs(a), abs(b))


def corroborate(
    primary: dict, rederived: dict, rubric: tuple[Rule, ...] = RUBRIC
) -> Corroboration:
    """Compare the scoring view of two independent readings of the same lead."""
    fired_primary = tuple(r.name for r in rubric if r.fires(primary))
    fired_rederived = tuple(r.name for r in rubric if r.fires(rederived))

    deltas: list[Delta] = []

    # Score-material disagreements: a rule fires under one reading and not the other.
    flipped_fields: set[str] = set()
    for rule in rubric:
        fp, fr = rule.name in fired_primary, rule.name in fired_rederived
        if fp != fr:
            flipped_fields.add(rule.field)
            deltas.append(
                Delta(
                    field=rule.name,
                    primary=primary.get(rule.field),
                    rederived=rederived.get(rule.field),
                    effect="rule_flipped",
                )
            )

    # Score-neutral drift: same rules fire, but the readings disagree materially.
    for field in _NUMERIC_FIELDS:
        if field in flipped_fields:
            continue  # already reported as a flip
        a, b = primary.get(field, 0) or 0, rederived.get(field, 0) or 0
        if not _numbers_close(a, b):
            deltas.append(Delta(field=field, primary=a, rederived=b, effect="value_drift"))
    for field in _CATEGORICAL_FIELDS:
        if field in flipped_fields:
            continue
        a, b = primary.get(field) or None, rederived.get(field) or None
        if a != b:
            deltas.append(Delta(field=field, primary=a, rederived=b, effect="value_drift"))

    if any(d.effect == "rule_flipped" for d in deltas):
        verdict = EXCLUDED
    elif deltas:
        verdict = REVIEW
    else:
        verdict = CONFIRMED

    return Corroboration(
        verdict=verdict,
        deltas=tuple(deltas),
        fired_primary=fired_primary,
        fired_rederived=fired_rederived,
    )
