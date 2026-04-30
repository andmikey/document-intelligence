"""LangGraph node implementations for the multi-agent pipeline.

Nodes
-----
classifier_node   — calls backend.classify(), writes classifier_* fields
extractor_node    — calls backend.extract(), parses into ExtractedFields schema
scorer_node       — runs deterministic rules, aggregates score, builds summary

Each node receives the full GraphState dict and returns a partial dict of
only the fields it sets. LangGraph merges this back into the running state.
"""

from __future__ import annotations

import time
from typing import Any

from pipeline.agent.backends import BaseLLMBackend
from pipeline.agent.state import GraphState
from pipeline.schemas import ExtractedFields, RuleResult
from pipeline.score import aggregate_score, assign_label, build_summary, run_rules

# ---------------------------------------------------------------------------
# Classifier node
# ---------------------------------------------------------------------------


def classifier_node(state: GraphState, backend: BaseLLMBackend) -> dict[str, Any]:
    """Classify the document; return category + confidence only."""
    start = time.time()
    try:
        result = backend.classify(state["image_b64"])
        category = str(result.get("category", "other"))
        confidence = float(result.get("category_confidence", 0.0))
    except Exception as exc:
        category = "other"
        confidence = 0.0

    latency_ms = int((time.time() - start) * 1000)
    timings = dict(state.get("step_timings") or {})
    timings["classifier"] = latency_ms

    return {
        "classifier_category": category,
        "classifier_confidence": confidence,
        "classifier_reviewed": False,
        "analyst_category": None,
        "analyst_confidence": None,
        "step_timings": timings,
    }


# ---------------------------------------------------------------------------
# Extractor node
# ---------------------------------------------------------------------------


def _parse_extracted_fields(raw: dict[str, Any]) -> tuple[ExtractedFields, list[str]]:
    """Parse a raw dict into ExtractedFields with warnings for missing/bad fields."""
    from pydantic import ValidationError

    warnings: list[str] = []

    # Check for expected fields before validation
    expected = set(ExtractedFields.model_fields.keys())
    present = set(raw.keys()) if isinstance(raw, dict) else set()
    for field in sorted(expected - present):
        warnings.append(f"{field}: not returned by model")

    # Attempt Pydantic parse; strip bad fields and re-validate on error
    try:
        fields = ExtractedFields(**{k: v for k, v in raw.items() if k in expected})
    except ValidationError as exc:
        for error in exc.errors():
            field_path = ".".join(str(loc) for loc in error["loc"])
            etype = "missing" if "missing" in error["type"] else "wrong_type"
            warnings.append(f"{field_path}: {etype}")
            raw.pop(field_path.split(".")[0], None)
        try:
            fields = ExtractedFields(**{k: v for k, v in raw.items() if k in expected})
        except Exception:
            fields = ExtractedFields()
            warnings.append("extraction: validation failed after cleanup")

    return fields, warnings


def extractor_node(state: GraphState, backend: BaseLLMBackend) -> dict[str, Any]:
    """Extract structured fields given the confirmed category."""
    category = (
        state.get("analyst_category") or state.get("classifier_category") or "other"
    )
    start = time.time()
    try:
        raw = backend.extract(state["image_b64"], category)
        if not isinstance(raw, dict):
            raw = {}
    except Exception:
        raw = {}

    latency_ms = int((time.time() - start) * 1000)

    # Strip any _error key before parsing
    raw.pop("_error", None)

    fields, warnings = _parse_extracted_fields(raw)

    timings = dict(state.get("step_timings") or {})
    timings["extractor"] = latency_ms

    return {
        "extracted_fields": fields.model_dump(),
        "extraction_warnings": warnings,
        "extractor_latency_ms": latency_ms,
        "fields_reviewed": False,
        "analyst_fields": None,
        "step_timings": timings,
        "effective_category": category,
    }


# ---------------------------------------------------------------------------
# Scorer node
# ---------------------------------------------------------------------------


def scorer_node(state: GraphState) -> dict[str, Any]:
    """Run deterministic rules on the (possibly analyst-edited) fields."""
    start = time.time()

    # Prefer analyst-edited fields if the analyst reviewed them
    raw_fields: dict[str, Any] = (
        state.get("analyst_fields")
        if state.get("fields_reviewed") and state.get("analyst_fields") is not None
        else state.get("extracted_fields") or {}
    )

    try:
        fields = ExtractedFields(**raw_fields)
        rule_results = run_rules(fields)
        risk_score = aggregate_score(rule_results)
        label = assign_label(risk_score)
        summary = build_summary(rule_results, label)
    except Exception:
        rule_results = []
        risk_score = 0.0
        label = "low"
        summary = "Scoring failed — manual review required."

    latency_ms = int((time.time() - start) * 1000)
    timings = dict(state.get("step_timings") or {})
    timings["scorer"] = latency_ms

    return {
        "rule_results": [r.model_dump() for r in rule_results],
        "risk_score": risk_score,
        "risk_label": label,
        "summary": summary,
        "step_timings": timings,
    }
