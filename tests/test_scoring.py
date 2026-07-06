"""Tests for the deterministic scoring core.

The headline test does not check whether the reason is well written. It checks that the
reason is not LYING: the points it names must sum to the score. Those are different jobs,
and in a review only the second one keeps you honest.
"""

import re

from core.scoring import RUBRIC, score_lead

SAMPLE_LEADS = [
    {"monthly_spend": 6000, "seats": 30, "renewed": True, "contact_role": "vp"},
    {"monthly_spend": 9000, "seats": 10, "renewed": False, "contact_role": "analyst"},
    {"monthly_spend": 0, "seats": 0},  # nothing fires
    {"monthly_spend": 12000, "seats": 40, "renewed": True, "contact_role": "owner"},  # all fire
]


def test_reason_points_sum_to_score():
    """The audit-trail tripwire: parse the reason's own +N tokens and check they add up."""
    for lead in SAMPLE_LEADS:
        result = score_lead(lead)
        named = [int(points) for points in re.findall(r"\+(\d+)", result.reason)]
        assert sum(named) == result.raw, result.reason
        assert result.reconciles()


def test_the_60_not_40_case():
    """The canonical row from the write-up: spend below the 8000 line, so the 40 never
    fires, and the reason must not claim spend as a reason. It is a 60 because team size,
    a decision-maker contact, and a prior renewal fired, and nothing else did."""
    result = score_lead(
        {"monthly_spend": 6000, "seats": 30, "renewed": True, "contact_role": "vp"}
    )
    assert result.score == 60  # 35 + 15 + 10, spend contributes 0
    assert "monthly spend" not in result.reason  # it did not fire, so it is not claimed


def test_empty_lead_scores_zero_with_an_honest_reason():
    """No signals is a defensible zero with a reason that says so, not a blank."""
    result = score_lead({})
    assert result.score == 0
    assert result.raw == 0
    assert "no signals fired" in result.reason
    assert result.reconciles()


def test_weights_top_out_at_the_cap():
    """When everything fires the raw sum lands exactly on the cap, so `min` never has to
    silently absorb points. If a future rubric edit breaks this, the cap note fires."""
    result = score_lead(
        {"monthly_spend": 99999, "seats": 999, "renewed": True, "contact_role": "owner"}
    )
    assert result.raw == 100
    assert result.score == 100
    assert "capped from" not in result.reason


def test_cap_is_named_never_silent_when_overshooting():
    """If a rubric ever overshoots the cap, the result stays reconcilable (parts sum to
    raw) and the reason discloses the cap rather than hiding the lost points."""
    loud_rubric = RUBRIC + (
        __import__("core.scoring", fromlist=["Rule"]).Rule(
            name="bonus",
            points=20,
            fires=lambda lead: True,
            because=lambda lead: "+20 synthetic overshoot rule",
        ),
    )
    result = score_lead(
        {"monthly_spend": 12000, "seats": 40, "renewed": True, "contact_role": "owner"},
        rubric=loud_rubric,
    )
    assert result.raw == 120
    assert result.score == 100
    assert "capped from 120" in result.reason
    assert result.reconciles()  # parts still sum to raw, the cap is disclosed not absorbed
