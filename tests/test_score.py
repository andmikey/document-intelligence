"""Unit tests for scoring logic."""

from pipeline.schemas import ExtractedFields, RuleResult
from pipeline.score import BUCKET_CAPS, aggregate_score, assign_label, build_summary


def test_bucket_cap_prevents_double_counting():
    """Test that bucket caps prevent correlated rules from dominating score."""
    # Create two triggered rules in the same bucket whose weights sum > cap
    # Contact bucket cap is 0.30
    # UnknownContactRule (0.20) + PersonalMessagingPlatformRule (0.15) = 0.35 > 0.30
    results = [
        RuleResult(
            rule_id="unknown_contact_initiated",
            triggered=True,
            weight=0.20,
            explanation="unknown contact initiated conversation",
        ),
        RuleResult(
            rule_id="personal_messaging_platform",
            triggered=True,
            weight=0.15,
            explanation="personal messaging platform used",
        ),
    ]

    score = aggregate_score(results)

    # The contact bucket contribution should be capped at 0.30
    # Normalized by sum(BUCKET_CAPS) = 1.10
    # Expected: 0.30 / 1.10 = 0.27 (rounded to 2dp)
    expected_max = BUCKET_CAPS["contact"] / sum(BUCKET_CAPS.values())
    assert score <= round(expected_max, 2)
    assert score == 0.27


def test_untriggered_rules_do_not_contribute():
    """Test that untriggered rules contribute zero to the score."""
    results = [
        RuleResult(
            rule_id="crypto_compensation",
            triggered=False,
            weight=0.35,
            explanation="",
        ),
        RuleResult(
            rule_id="unknown_contact_initiated",
            triggered=False,
            weight=0.20,
            explanation="",
        ),
        RuleResult(
            rule_id="third_party_referral",
            triggered=False,
            weight=0.20,
            explanation="",
        ),
    ]

    score = aggregate_score(results)
    assert score == 0.0


def test_label_thresholds():
    """Test that risk labels are assigned at correct thresholds."""
    assert assign_label(0.20) == "low"
    assert assign_label(0.34) == "low"
    assert assign_label(0.35) == "medium"
    assert assign_label(0.50) == "medium"
    assert assign_label(0.64) == "medium"
    assert assign_label(0.65) == "high"
    assert assign_label(0.80) == "high"


def test_no_triggered_rules_summary():
    """Test summary when no rules are triggered."""
    all_untriggered = [
        RuleResult(
            rule_id="crypto_compensation",
            triggered=False,
            weight=0.35,
            explanation="",
        ),
        RuleResult(
            rule_id="unknown_contact_initiated",
            triggered=False,
            weight=0.20,
            explanation="",
        ),
    ]

    summary = build_summary(all_untriggered, "low")
    assert summary == "No significant risk signals detected."


def test_triggered_rules_summary():
    """Test summary formatting with triggered rules."""
    results = [
        RuleResult(
            rule_id="crypto_compensation",
            triggered=True,
            weight=0.35,
            explanation="cryptocurrency compensation mentioned",
        ),
        RuleResult(
            rule_id="third_party_referral",
            triggered=True,
            weight=0.20,
            explanation="third-party referral present",
        ),
        RuleResult(
            rule_id="unknown_contact_initiated",
            triggered=False,
            weight=0.20,
            explanation="",
        ),
    ]

    summary = build_summary(results, "high")
    assert (
        summary
        == "High risk: cryptocurrency compensation mentioned; third-party referral present."
    )
