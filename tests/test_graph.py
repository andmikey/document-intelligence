"""Tests for the LangGraph multi-agent pipeline graph.

All tests use LocalFixtureBackend so zero network calls are made.
The graph is built fresh for each test to avoid checkpointer state leaking.
"""

import uuid
from typing import Any

import pytest

from pipeline.agent.backends import LocalFixtureBackend
from pipeline.agent.graph import (
    assemble_output,
    build_graph,
    resume_after_classifier,
    resume_after_fields,
    start_graph,
)
from pipeline.schemas import ExtractedFields, PipelineOutput


def _fresh_graph():
    """Return a compiled graph backed by LocalFixtureBackend."""
    return build_graph(LocalFixtureBackend())


def _run_full(graph=None, file_id: str | None = None) -> dict[str, Any]:
    """Run the graph end-to-end with no analyst edits and return final state."""
    if graph is None:
        graph = _fresh_graph()
    fid = file_id or str(uuid.uuid4())

    state = start_graph(graph, file_id=fid, image_b64="test_image_b64")
    state = resume_after_classifier(
        graph,
        file_id=fid,
        analyst_category=state.get("classifier_category", "other"),
        analyst_confidence=float(state.get("classifier_confidence") or 0.0),
    )
    state = resume_after_fields(
        graph, file_id=fid, analyst_fields=state.get("extracted_fields") or {}
    )
    return state


# ---------------------------------------------------------------------------
# start_graph — classifier node
# ---------------------------------------------------------------------------


class TestStartGraph:
    def test_returns_classifier_category(self):
        state = start_graph(_fresh_graph(), file_id=str(uuid.uuid4()), image_b64="img")
        assert "classifier_category" in state
        assert state["classifier_category"] in [
            "chat_screenshot",
            "invoice",
            "marketplace_listing_screenshot",
            "website_screenshot",
            "other",
        ]

    def test_returns_classifier_confidence_float(self):
        state = start_graph(_fresh_graph(), file_id=str(uuid.uuid4()), image_b64="img")
        assert isinstance(state.get("classifier_confidence"), float)
        assert 0.0 <= state["classifier_confidence"] <= 1.0

    def test_graph_not_yet_finished(self):
        """After start_graph, scoring fields should not be present."""
        state = start_graph(_fresh_graph(), file_id=str(uuid.uuid4()), image_b64="img")
        assert state.get("risk_score") is None
        assert state.get("rule_results") is None


# ---------------------------------------------------------------------------
# resume_after_classifier — extractor node
# ---------------------------------------------------------------------------


class TestResumeAfterClassifier:
    def test_extracted_fields_present(self):
        g = _fresh_graph()
        fid = str(uuid.uuid4())
        state = start_graph(g, file_id=fid, image_b64="img")
        state = resume_after_classifier(
            g,
            file_id=fid,
            analyst_category="invoice",
            analyst_confidence=0.9,
        )
        assert "extracted_fields" in state
        assert isinstance(state["extracted_fields"], dict)

    def test_analyst_category_injected(self):
        g = _fresh_graph()
        fid = str(uuid.uuid4())
        start_graph(g, file_id=fid, image_b64="img")
        state = resume_after_classifier(
            g, file_id=fid, analyst_category="invoice", analyst_confidence=0.8
        )
        assert state.get("analyst_category") == "invoice"

    def test_extraction_warnings_is_list(self):
        g = _fresh_graph()
        fid = str(uuid.uuid4())
        start_graph(g, file_id=fid, image_b64="img")
        state = resume_after_classifier(
            g, file_id=fid, analyst_category="other", analyst_confidence=0.5
        )
        assert isinstance(state.get("extraction_warnings"), list)


# ---------------------------------------------------------------------------
# resume_after_fields — scorer node
# ---------------------------------------------------------------------------


class TestResumeAfterFields:
    def test_risk_score_in_range(self):
        state = _run_full()
        assert 0.0 <= state["risk_score"] <= 1.0

    def test_risk_label_valid(self):
        state = _run_full()
        assert state["risk_label"] in ("low", "medium", "high")

    def test_rule_results_list(self):
        state = _run_full()
        assert isinstance(state["rule_results"], list)
        for r in state["rule_results"]:
            assert "rule_id" in r
            assert "triggered" in r

    def test_summary_is_string(self):
        state = _run_full()
        assert isinstance(state.get("summary"), str)
        assert len(state["summary"]) > 0

    def test_analyst_fields_override_extractor_output(self):
        """Analyst-injected fields flow into the scorer."""
        from pipeline import flags

        g = _fresh_graph()
        fid = str(uuid.uuid4())
        state = start_graph(g, file_id=fid, image_b64="img")
        state = resume_after_classifier(
            g,
            file_id=fid,
            analyst_category=state.get("classifier_category", "other"),
            analyst_confidence=float(state.get("classifier_confidence") or 0.0),
        )
        # Inject a field edit that should trigger crypto compensation rule
        state = resume_after_fields(
            g,
            file_id=fid,
            analyst_fields={
                "red_flags": [flags.CRYPTO_COMPENSATION],
                "platform": None,
                "entity_name": None,
                "amount": None,
                "currency": None,
                "date": None,
                "counterparty": None,
                "contact_details": None,
            },
        )
        triggered = {r["rule_id"] for r in state["rule_results"] if r["triggered"]}
        assert "crypto_compensation" in triggered

    def test_step_timings_recorded(self):
        state = _run_full()
        timings = state.get("step_timings") or {}
        assert "classifier" in timings
        assert "extractor" in timings
        assert "scorer" in timings


# ---------------------------------------------------------------------------
# assemble_output
# ---------------------------------------------------------------------------


class TestAssembleOutput:
    def test_returns_pipeline_output_instance(self):
        fid = str(uuid.uuid4())
        state = _run_full(file_id=fid)
        output = assemble_output(state, fid)
        assert isinstance(output, PipelineOutput)

    def test_file_id_matches(self):
        fid = str(uuid.uuid4())
        state = _run_full(file_id=fid)
        output = assemble_output(state, fid)
        assert output.file_id == fid

    def test_pipeline_mode_is_multi_agent(self):
        fid = str(uuid.uuid4())
        state = _run_full(file_id=fid)
        output = assemble_output(state, fid)
        assert output.processing_metadata.pipeline_mode == "multi-agent"

    def test_analyst_category_override_reflected(self):
        g = _fresh_graph()
        fid = str(uuid.uuid4())
        state = start_graph(g, file_id=fid, image_b64="img")
        state = resume_after_classifier(
            g, file_id=fid, analyst_category="invoice", analyst_confidence=0.95
        )
        state = resume_after_fields(
            g, file_id=fid, analyst_fields=state.get("extracted_fields") or {}
        )
        output = assemble_output(state, fid)
        assert output.category == "invoice"

    def test_analyst_category_change_in_interventions(self):
        g = _fresh_graph()
        fid = str(uuid.uuid4())
        state = start_graph(g, file_id=fid, image_b64="img")
        original_cat = state.get("classifier_category", "other")
        # Pick a different category to force a recorded intervention
        other_cat = "invoice" if original_cat != "invoice" else "other"
        state = resume_after_classifier(
            g, file_id=fid, analyst_category=other_cat, analyst_confidence=0.9
        )
        state = resume_after_fields(
            g, file_id=fid, analyst_fields=state.get("extracted_fields") or {}
        )
        output = assemble_output(state, fid)
        interventions = output.processing_metadata.analyst_interventions
        assert any("category changed" in i for i in interventions)

    def test_fields_review_recorded_in_interventions(self):
        fid = str(uuid.uuid4())
        state = _run_full(file_id=fid)
        output = assemble_output(state, fid)
        interventions = output.processing_metadata.analyst_interventions
        assert any("fields reviewed" in i for i in interventions)

    def test_schema_matches_pipeline_output(self):
        """PipelineOutput.model_dump() must be JSON-serialisable without errors."""
        fid = str(uuid.uuid4())
        state = _run_full(file_id=fid)
        output = assemble_output(state, fid)
        import json

        serialised = json.dumps(output.model_dump())
        assert len(serialised) > 0
