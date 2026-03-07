"""Pydantic models for all inputs and outputs."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ExtractedFields(BaseModel):
    """Output of the LLM extraction step.

    Fields match the spec exactly. Rules must use only these fields.
    """

    model_config = ConfigDict(extra="ignore")

    entity_name: str | None = None
    amount: float | None = None
    currency: str | None = None
    date: str | None = None
    counterparty: str | None = None
    platform: str | None = None
    contact_details: str | None = None
    red_flags: list[str] = []  # descriptive labels, not risk judgements


class ProcessingMetadata(BaseModel):
    """Populated from ExtractionResult, included in final output."""

    model_config = ConfigDict(extra="ignore")

    model_used: str
    latency_ms: int
    extraction_warnings: list[str]  # missing fields, parse issues, etc.


class ExtractionResult(BaseModel):
    """Internal result of the extraction step, not the final output."""

    model_config = ConfigDict(extra="ignore")

    category: Literal[
        "invoice",
        "marketplace_listing_screenshot",
        "chat_screenshot",
        "website_screenshot",
        "other",
    ]
    category_confidence: float
    extracted_fields: ExtractedFields
    processing_metadata: ProcessingMetadata


class RuleResult(BaseModel):
    """Output of a single scoring rule."""

    model_config = ConfigDict(extra="ignore")

    rule_id: str
    triggered: bool
    weight: float
    explanation: str


class PipelineOutput(BaseModel):
    """The final output contract returned to the UI and saved as JSON."""

    model_config = ConfigDict(extra="ignore")

    file_id: str
    category: str
    category_confidence: float
    extracted_fields: ExtractedFields
    scoring_rules: list[RuleResult]
    risk_score: float
    risk_label: Literal["low", "medium", "high"]
    summary: str
    processing_metadata: ProcessingMetadata
