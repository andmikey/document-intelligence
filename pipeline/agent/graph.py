"""LangGraph graph definition for the multi-agent pipeline.

Graph structure
---------------
  [classify] -> [await_classifier_review] -> [extract] -> [await_fields_review] -> [score]

  await_classifier_review and await_fields_review are INTERRUPT nodes:
  the graph halts and returns state to the Streamlit UI which renders the
  review form. When the analyst clicks Continue, the UI injects analyst edits
  via graph.update_state() then resumes with graph.invoke(None, config=config).

Usage
-----
  from pipeline.agent.graph import build_graph, start_graph, resume_after_classifier
  from pipeline.agent.graph import resume_after_fields, assemble_output

  graph = build_graph()
  state = start_graph(graph, file_id=..., image_b64=...)  # halts after classify
  # UI shows classifier review form
  state = resume_after_classifier(graph, file_id=..., analyst_category=..., analyst_confidence=...)
  # halts after extract
  # UI shows field-edit form
  state = resume_after_fields(graph, file_id=..., analyst_fields={...})
  # scorer runs; state is final
  output = assemble_output(state, file_id)
"""

from __future__ import annotations

from typing import Any, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from pipeline.agent.backends import BaseLLMBackend, get_backend
from pipeline.agent.nodes import classifier_node, extractor_node, scorer_node
from pipeline.agent.state import GraphState

# ---------------------------------------------------------------------------
# Node names (constants to avoid typos)
# ---------------------------------------------------------------------------

CLASSIFY = "classify"
AWAIT_CLASSIFIER_REVIEW = "await_classifier_review"
EXTRACT = "extract"
AWAIT_FIELDS_REVIEW = "await_fields_review"
SCORE = "score"


# ---------------------------------------------------------------------------
# Node wrappers (bind backend at graph-build time)
# ---------------------------------------------------------------------------


def _make_classifier(backend: BaseLLMBackend):
    def _classify(state: GraphState) -> dict[str, Any]:
        return classifier_node(state, backend)

    _classify.__name__ = CLASSIFY
    return _classify


def _make_extractor(backend: BaseLLMBackend):
    def _extract(state: GraphState) -> dict[str, Any]:
        return extractor_node(state, backend)

    _extract.__name__ = EXTRACT
    return _extract


# ---------------------------------------------------------------------------
# Interrupt nodes — pass-through; graph pauses BEFORE these via interrupt_before
# ---------------------------------------------------------------------------


def _await_classifier_review(state: GraphState) -> dict[str, Any]:
    return {}


def _await_fields_review(state: GraphState) -> dict[str, Any]:
    return {}


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_graph(backend: BaseLLMBackend | None = None, headless: bool = False) -> Any:
    """Build and compile the StateGraph with a MemorySaver checkpointer.

    MemorySaver is required for interrupt_before to work — it persists the
    graph state between the halt and the resume call.

    Args:
        backend: LLM backend to use. Defaults to get_backend().
        headless: When True, compile without interrupt points so the graph
            runs end-to-end in a single invoke() call. Intended for automated
            pipelines and evals where human-in-the-loop review is not needed.

    Returns:
        Compiled LangGraph graph (CompiledStateGraph).
    """
    if backend is None:
        backend = get_backend()

    builder = StateGraph(GraphState)

    builder.add_node(CLASSIFY, _make_classifier(backend))
    builder.add_node(AWAIT_CLASSIFIER_REVIEW, _await_classifier_review)
    builder.add_node(EXTRACT, _make_extractor(backend))
    builder.add_node(AWAIT_FIELDS_REVIEW, _await_fields_review)
    builder.add_node(SCORE, scorer_node)

    builder.set_entry_point(CLASSIFY)
    builder.add_edge(CLASSIFY, AWAIT_CLASSIFIER_REVIEW)
    builder.add_edge(AWAIT_CLASSIFIER_REVIEW, EXTRACT)
    builder.add_edge(EXTRACT, AWAIT_FIELDS_REVIEW)
    builder.add_edge(AWAIT_FIELDS_REVIEW, SCORE)
    builder.add_edge(SCORE, END)

    # MemorySaver checkpointer is mandatory for interrupt_before to function
    checkpointer = MemorySaver()
    interrupt_nodes = [] if headless else [AWAIT_CLASSIFIER_REVIEW, AWAIT_FIELDS_REVIEW]
    graph = builder.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_nodes,
    )
    return graph


# ---------------------------------------------------------------------------
# Run helpers — called by the Streamlit UI at each stage
# ---------------------------------------------------------------------------


def _config(file_id: str) -> dict:
    """Build the LangGraph thread config for a given file_id."""
    return {"configurable": {"thread_id": file_id}}


def start_graph(
    graph: Any,
    *,
    file_id: str,
    image_b64: str,
) -> dict[str, Any]:
    """Start a fresh run. Returns state after classifier node (graph halted).

    The returned dict contains classifier_category and classifier_confidence.
    """
    initial: GraphState = {
        "file_id": file_id,
        "image_b64": image_b64,
        "pipeline_mode": "multi-agent",
        "step_timings": {},
        "error": None,
        "trace_id": None,
        "langsmith_run_url": None,
    }
    result = graph.invoke(initial, config=_config(file_id))
    # invoke() returns the state snapshot dict when interrupted
    return result if isinstance(result, dict) else dict(result)


def resume_after_classifier(
    graph: Any,
    *,
    file_id: str,
    analyst_category: str,
    analyst_confidence: float,
) -> dict[str, Any]:
    """Inject analyst-confirmed category then resume.

    Runs the extractor node and halts again at the field-edit checkpoint.
    Returns the updated state dict.
    """
    cfg = _config(file_id)
    graph.update_state(
        cfg,
        {
            "analyst_category": analyst_category,
            "analyst_confidence": analyst_confidence,
            "classifier_reviewed": True,
        },
    )
    result = graph.invoke(None, config=cfg)
    return result if isinstance(result, dict) else dict(result)


def resume_after_fields(
    graph: Any,
    *,
    file_id: str,
    analyst_fields: dict[str, Any],
) -> dict[str, Any]:
    """Inject analyst-edited fields then resume.

    Runs the scorer node through to END. Returns the final state dict.
    """
    cfg = _config(file_id)
    graph.update_state(
        cfg,
        {
            "analyst_fields": analyst_fields,
            "fields_reviewed": True,
        },
    )
    result = graph.invoke(None, config=cfg)
    return result if isinstance(result, dict) else dict(result)


# ---------------------------------------------------------------------------
# Output assembly
# ---------------------------------------------------------------------------


def assemble_output(state: dict[str, Any], file_id: str):
    """Convert final GraphState dict into a PipelineOutput instance."""
    from pipeline.schemas import (
        ExtractedFields,
        PipelineOutput,
        ProcessingMetadata,
        RuleResult,
    )

    # Final category: analyst override beats classifier output
    category = (
        state.get("analyst_category") or state.get("classifier_category") or "other"
    )
    confidence = state.get("analyst_confidence")
    if confidence is None:
        confidence = float(state.get("classifier_confidence") or 0.0)

    # Final fields: analyst edits beat extractor output
    fields_dict: dict[str, Any] = (
        state.get("analyst_fields")
        if state.get("fields_reviewed") and state.get("analyst_fields") is not None
        else state.get("extracted_fields") or {}
    )
    fields = ExtractedFields(
        **{k: v for k, v in fields_dict.items() if k in ExtractedFields.model_fields}
    )

    rule_results = [RuleResult(**r) for r in (state.get("rule_results") or [])]

    # Build analyst intervention audit trail
    analyst_interventions: list[str] = []
    if state.get("classifier_reviewed") and state.get("analyst_category"):
        orig = state.get("classifier_category", "")
        if state["analyst_category"] != orig:
            analyst_interventions.append(
                f"category changed: {orig} → {state['analyst_category']}"
            )
    if state.get("fields_reviewed") and state.get("analyst_fields") is not None:
        analyst_interventions.append("extracted fields reviewed by analyst")

    timings: dict[str, int] = state.get("step_timings") or {}
    total_latency = sum(timings.values())

    metadata = ProcessingMetadata(
        model_used=state.get("extractor_model_used") or "local_fixture",
        latency_ms=total_latency,
        extraction_warnings=state.get("extraction_warnings") or [],
        analyst_interventions=analyst_interventions,
        pipeline_mode="multi-agent",
    )

    return PipelineOutput(
        file_id=file_id,
        category=category,
        category_confidence=confidence,
        extracted_fields=fields,
        scoring_rules=rule_results,
        risk_score=float(state.get("risk_score") or 0.0),
        risk_label=state.get("risk_label") or "low",
        summary=state.get("summary") or "",
        processing_metadata=metadata,
    )
