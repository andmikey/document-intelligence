"""Abstract base class for scoring rules."""

from abc import ABC, abstractmethod

from pipeline.schemas import ExtractedFields, RuleResult


class BaseRule(ABC):
    """Base class for all scoring rules.

    Attributes:
        rule_id: Unique snake_case identifier
        weight: Contribution to risk score if triggered (0-1)
        bucket: Thematic group for capped aggregation
    """

    rule_id: str
    weight: float
    bucket: str

    @abstractmethod
    def evaluate(self, fields: ExtractedFields) -> RuleResult:
        """Evaluate the rule against extracted fields.

        Must return a RuleResult regardless of outcome.
        Must not raise exceptions — catch internally and return
        triggered=False with an explanation if something goes wrong.

        Args:
            fields: Extracted fields from the document

        Returns:
            RuleResult with evaluation outcome
        """
        ...
