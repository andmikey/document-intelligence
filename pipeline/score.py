"""Scoring logic for risk assessment."""

from typing import Literal

from pipeline.constants import RISK_THRESHOLD_LOW_MEDIUM, RISK_THRESHOLD_MEDIUM_HIGH
from pipeline.rules import RULES
from pipeline.schemas import ExtractedFields, RuleResult

# Bucket caps for aggregation
BUCKET_CAPS: dict[str, float] = {
    "compensation": 0.40,
    "contact": 0.30,
    "recruitment": 0.40,
}


def run_rules(fields: ExtractedFields) -> list[RuleResult]:
    """Run all rules against extracted fields.

    Args:
        fields: Extracted fields from document

    Returns:
        List of all RuleResults (triggered and not triggered)
    """
    results = []
    for rule in RULES:
        result = rule.evaluate(fields)
        results.append(result)
    return results


def aggregate_score(results: list[RuleResult]) -> float:
    """Aggregate triggered rule weights into a composite score.

    Groups rules by bucket, caps each bucket's contribution, then
    normalizes to 0-1 range.

    Args:
        results: List of RuleResults

    Returns:
        Normalized risk score (0-1), rounded to 2 decimal places
    """
    # Group triggered rules by bucket
    bucket_scores: dict[str, float] = {}

    for result in results:
        if not result.triggered:
            continue

        # Find the rule to get its bucket
        rule = next((r for r in RULES if r.rule_id == result.rule_id), None)
        if rule is None:
            continue

        bucket = rule.bucket
        if bucket not in bucket_scores:
            bucket_scores[bucket] = 0.0

        bucket_scores[bucket] += result.weight

    # Cap each bucket
    capped_total = 0.0
    for bucket, score in bucket_scores.items():
        cap = BUCKET_CAPS.get(bucket, 1.0)
        capped_score = min(score, cap)
        capped_total += capped_score

    # Normalize by sum of all caps
    normalizer = sum(BUCKET_CAPS.values())
    normalized_score = capped_total / normalizer

    # Round to 2 decimal places
    return round(normalized_score, 2)


def assign_label(score: float) -> Literal["low", "medium", "high"]:
    """Assign risk label based on score thresholds.

    Args:
        score: Normalized risk score (0-1)

    Returns:
        Risk label: "low", "medium", or "high"
    """
    if score < RISK_THRESHOLD_LOW_MEDIUM:
        return "low"
    elif score < RISK_THRESHOLD_MEDIUM_HIGH:
        return "medium"
    else:
        return "high"


def build_summary(results: list[RuleResult], label: str) -> str:
    """Build human-readable summary from triggered rules.

    Args:
        results: List of RuleResults
        label: Risk label

    Returns:
        Human-readable summary string
    """
    # Collect explanations from triggered rules only
    explanations = [r.explanation for r in results if r.triggered and r.explanation]

    if not explanations:
        return "No significant risk signals detected."

    # Join with semicolons
    joined = "; ".join(explanations)

    return f"{label.capitalize()} risk: {joined}."


def score(fields: ExtractedFields) -> tuple[list[RuleResult], float, str, str]:
    """Orchestrate scoring: run rules, aggregate, assign label, build summary.

    Args:
        fields: Extracted fields from document

    Returns:
        Tuple of (rule_results, risk_score, label, summary)
    """
    try:
        rule_results = run_rules(fields)
        risk_score = aggregate_score(rule_results)
        label = assign_label(risk_score)
        summary = build_summary(rule_results, label)
        return rule_results, risk_score, label, summary
    except Exception:
        # On any exception, return safe defaults
        return [], 0.0, "low", "Scoring failed — manual review required."
