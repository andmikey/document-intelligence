import json
from dataclasses import dataclass

from pydantic_evals.evaluators import Evaluator, EvaluatorContext, LLMJudge

from pipeline.constants import LLM_MODEL_NAME


@dataclass
class JsonValid(Evaluator):
    """
    Deterministic. Asserts the pipeline output is valid, parseable JSON.
    This is a structural check — malformed JSON is not a hallucination but
    a robustness failure. It is always detectable without ground truth.
    """

    def evaluate(self, ctx: EvaluatorContext) -> float:
        try:
            if isinstance(ctx.output, str):
                json.loads(ctx.output)
            # if output is already a dict/Pydantic model it parsed successfully
            return 1.0
        except (json.JSONDecodeError, TypeError):
            return 0.0


@dataclass
class CategoryCorrect(Evaluator):
    """
    Deterministic. Asserts the predicted category matches the expected category.
    Exact equality is appropriate because category is a bounded Literal set:
    invoice | marketplace_listing_screenshot | chat_screenshot | website_screenshot | other
    """

    def evaluate(self, ctx: EvaluatorContext) -> float:
        expected = ctx.expected_output.get("category")
        actual = (
            ctx.output.get("category")
            if isinstance(ctx.output, dict)
            else getattr(ctx.output, "category", None)
        )
        return 1.0 if actual == expected else 0.0


@dataclass
class RiskLabelCorrect(Evaluator):
    """
    Deterministic. Asserts the end-to-end risk_label matches the expected label.
    This is the highest-value single eval because it exercises the full pipeline
    in one assertion — ingestion, extraction, scoring, and label assignment.
    Exact equality is appropriate: risk_label is a bounded Literal["low","medium","high"].
    """

    def evaluate(self, ctx: EvaluatorContext) -> float:
        expected = ctx.expected_output.get("risk_label")
        actual = (
            ctx.output.get("risk_label")
            if isinstance(ctx.output, dict)
            else getattr(ctx.output, "risk_label", None)
        )
        return 1.0 if actual == expected else 0.0


@dataclass
class AmountCorrect(Evaluator):
    """
    Deterministic. Asserts the extracted amount matches the expected value.
    Exact numeric equality (after float coercion) is appropriate because amount
    is an unambiguous numeric field — there is a single correct value in the document.
    """

    def evaluate(self, ctx: EvaluatorContext) -> float:
        expected_fields = ctx.expected_output.get("extracted_fields", {})
        expected = expected_fields.get("amount")
        output_fields = (
            ctx.output.get("extracted_fields", {})
            if isinstance(ctx.output, dict)
            else getattr(ctx.output, "extracted_fields", {})
        )
        actual = (
            output_fields.get("amount")
            if isinstance(output_fields, dict)
            else getattr(output_fields, "amount", None)
        )
        if expected is None and actual is None:
            return 1.0
        try:
            return 1.0 if float(actual) == float(expected) else 0.0
        except (TypeError, ValueError):
            return 0.0


@dataclass
class CurrencyCorrect(Evaluator):
    """
    Deterministic. Asserts the extracted currency matches expected, case-insensitive.
    Exact equality (normalised) is appropriate — currency codes are unambiguous.
    """

    def evaluate(self, ctx: EvaluatorContext) -> float:
        expected_fields = ctx.expected_output.get("extracted_fields", {})
        expected = expected_fields.get("currency")
        output_fields = (
            ctx.output.get("extracted_fields", {})
            if isinstance(ctx.output, dict)
            else getattr(ctx.output, "extracted_fields", {})
        )
        actual = (
            output_fields.get("currency")
            if isinstance(output_fields, dict)
            else getattr(output_fields, "currency", None)
        )
        if expected is None and actual is None:
            return 1.0
        if expected is None or actual is None:
            return 0.0
        return 1.0 if actual.strip().upper() == expected.strip().upper() else 0.0


# LLM-as-judge evaluators
# Used for freeform fields where exact string matching is too strict —
# valid extractions may differ in formatting or phrasing from the expected string.
# Also used for red_flags to assess whether entries contain evaluative language,
# which requires semantic understanding rather than simple string matching.
#
# include_expected_output=True causes the judge to receive both ctx.output and
# ctx.expected_output so the rubric can compare them directly.
#
# The judge model is read from pipeline.constants.LLM_MODEL_NAME so it stays in
# sync with the extraction model and is changeable in one place.

contact_details_judge = LLMJudge(
    rubric=(
        "Compare the extracted contact_details field against the expected value. "
        "The field typically contains a phone number or other contact identifier. "
        "Accept minor formatting variations such as different spacing, dashes, "
        "or country code format (e.g. +447377618918 and +44 73 7761 8918 are equivalent). "
        "Return pass if the extracted value refers to the same contact as the expected "
        "value. Return fail if the value is absent, materially different, or refers to "
        "a different contact entirely."
    ),
    model=LLM_MODEL_NAME,
    include_expected_output=True,
)

counterparty_judge = LLMJudge(
    rubric=(
        "Compare the extracted counterparty field against the expected value. "
        "The counterparty should be the primary named contact the victim is speaking "
        "with directly — not secondary referrers mentioned in passing. "
        "Accept the name alone or with a role descriptor. "
        "Return pass if the extracted value identifies the same person as the expected "
        "value. Return fail if the value is absent, refers to a different person, or "
        "identifies a secondary contact rather than the primary one."
    ),
    model=LLM_MODEL_NAME,
    include_expected_output=True,
)

red_flags_judge = LLMJudge(
    rubric=(
        "The red_flags list should contain short descriptive labels for observable "
        "signals in the document — not fraud judgements. "
        "Each entry should describe what is observed (e.g. 'cryptocurrency_compensation_mentioned', "
        "'unknown_contact_initiated') rather than making evaluative claims "
        "(e.g. 'this is a scam', 'suspicious behaviour', 'likely fraud'). "
        "Return pass if all entries are descriptive observations with no evaluative language. "
        "Return fail if any entry contains words like: fraud, scam, suspicious, likely, "
        "probably, appears, seems, fake, illegitimate, criminal."
    ),
    model=LLM_MODEL_NAME,
)
