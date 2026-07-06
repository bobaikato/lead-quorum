"""Tests for score-space corroboration.

The invariant under test: a disagreement only kills the score when it changes which rules
fire. Value noise on the same side of every threshold downgrades confidence to REVIEW but
never silently alters the number, and a threshold flip always abstains, never averages.
"""

from core.corroboration import CONFIRMED, EXCLUDED, REVIEW, corroborate

BASE = {"monthly_spend": 6000, "seats": 30, "renewed": True, "contact_role": "vp"}


def test_identical_readings_confirm():
    result = corroborate(BASE, dict(BASE))
    assert result.verdict == CONFIRMED
    assert result.deltas == ()


def test_small_numeric_noise_still_confirms():
    # 6000 vs 6500 is within the 15% band and flips no rule: same score, same story.
    other = dict(BASE, monthly_spend=6500)
    assert corroborate(BASE, other).verdict == CONFIRMED


def test_material_drift_on_same_side_is_review_not_excluded():
    # seats 30 vs 45: both >= 25, so team_size fires either way and the score is
    # identical; but the readings clearly disagree, so confidence drops to REVIEW.
    other = dict(BASE, seats=45)
    result = corroborate(BASE, other)
    assert result.verdict == REVIEW
    assert any(d.field == "seats" and d.effect == "value_drift" for d in result.deltas)


def test_role_disagreement_within_decision_maker_set_is_review():
    # vp vs director: both count as decision makers, rule unchanged, values differ.
    other = dict(BASE, contact_role="director")
    result = corroborate(BASE, other)
    assert result.verdict == REVIEW


def test_threshold_flip_is_excluded_and_names_the_rule():
    # 7500 vs 9000 crosses the 8000 budget line: the two readings produce DIFFERENT
    # scores, so no single number is trustworthy. Abstain and say exactly why.
    a = dict(BASE, monthly_spend=7500)
    b = dict(BASE, monthly_spend=9000)
    result = corroborate(a, b)
    assert result.verdict == EXCLUDED
    flip = [d for d in result.deltas if d.effect == "rule_flipped"]
    assert flip and flip[0].field == "budget"
    assert flip[0].primary == 7500 and flip[0].rederived == 9000
    assert "abstaining" in result.summary()


def test_renewed_flip_is_excluded():
    other = dict(BASE, renewed=False)
    result = corroborate(BASE, other)
    assert result.verdict == EXCLUDED
    assert any(d.field == "prior_relationship" for d in result.deltas)


def test_flip_is_not_double_reported_as_drift():
    a = dict(BASE, monthly_spend=7500)
    b = dict(BASE, monthly_spend=9000)
    result = corroborate(a, b)
    spend_deltas = [d for d in result.deltas if "spend" in str(d.field) or d.field == "budget"]
    assert len(spend_deltas) == 1  # the flip, not flip + drift for the same field
