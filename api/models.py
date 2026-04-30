"""Pydantic request/response models for the FastAPI API.

These are distinct from pipeline/schemas.py: they describe the HTTP contract
between the frontend and this server, not the internal pipeline contract.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from pipeline.schemas import ExtractedFields, PipelineOutput


class SessionResponse(BaseModel):
    """Response from POST /api/sessions."""

    file_id: str
    # "classifier_review" when confidence is below threshold;
    # "fields_review" when the classifier is confident (or single-model auto-extracts).
    stage: Literal["classifier_review", "fields_review"]
    classifier_category: str
    classifier_confidence: float
    # Populated when stage == "fields_review" (extraction already ran)
    extracted_fields: Optional[dict[str, Any]] = None
    extraction_warnings: list[str] = []
    # Base64-encoded JPEG; needed so the review forms can show the source document.
    image_b64: str


class ConfirmCategoryRequest(BaseModel):
    category: str
    confidence: float = Field(ge=0.0, le=1.0)


class ConfirmCategoryResponse(BaseModel):
    stage: Literal["fields_review"] = "fields_review"
    extracted_fields: dict[str, Any]
    extraction_warnings: list[str] = []


class ConfirmFieldsRequest(BaseModel):
    fields: ExtractedFields


class ConfirmFieldsResponse(BaseModel):
    stage: Literal["complete"] = "complete"
    output: PipelineOutput
