"""LangGraph state model for one multi-agent pipeline run.

GraphState is the single dict-like object that flows through every node in
the graph. All fields are Optional so nodes can be added incrementally.

Field ownership:
  - image_b64, file_id               set by the caller before graph entry
  - classifier_category/confidence   set by classifier_node
  - analyst_category/confidence      set by HITL checkpoint (may equal classifier values)
  - extracted_fields, extraction_warnings  set by extractor_node
  - analyst_fields                   set by HITL field-edit checkpoint
  - rule_results, risk_score/label/summary  set by scorer_node
  - pipeline_mode                    "multi-agent" (always, in this state)
  - step_timings                     accumulated by each node
  - trace_id, langsmith_run_url      set by tracing layer when LangSmith is active
  - error                            set by any node on fatal failure
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Optional

from typing_extensions import TypedDict


class GraphState(TypedDict, total=False):
    # --- inputs ---
    file_id: str
    image_b64: str

    # --- classifier node outputs ---
    classifier_category: str
    classifier_confidence: float

    # --- analyst overrides from classifier HITL checkpoint ---
    # These are None until the analyst submits; then they are the confirmed values.
    analyst_category: Optional[str]
    analyst_confidence: Optional[float]
    classifier_reviewed: bool  # True once analyst has confirmed/edited

    # --- derived: whichever category flows into the extractor ---
    effective_category: str

    # --- extractor node outputs ---
    extracted_fields: Optional[dict[str, Any]]  # raw dict before Pydantic parse
    extraction_warnings: list[str]
    extractor_model_used: str
    extractor_latency_ms: int

    # --- analyst overrides from field-edit HITL checkpoint ---
    analyst_fields: Optional[dict[str, Any]]
    fields_reviewed: bool  # True once analyst has confirmed/edited

    # --- scorer node outputs ---
    rule_results: list[dict[str, Any]]
    risk_score: float
    risk_label: Literal["low", "medium", "high"]
    summary: str

    # --- metadata ---
    pipeline_mode: str
    step_timings: dict[str, int]  # node_name -> latency_ms
    trace_id: Optional[str]
    langsmith_run_url: Optional[str]
    error: Optional[str]
