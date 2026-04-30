"""Streamlit UI for document risk extraction.

Stage machine
-------------
  idle → classifying → [classifier_review] → extracting → fields_review → scoring → complete

  classifier_review is only shown when confidence < CLASSIFIER_CONFIDENCE_THRESHOLD.
  extracting is only used in multi-agent mode (single-model extracts everything in
  one call during the classifying stage).
  fields_review is always shown in both modes.

  All LLM calls happen inside st.spinner blocks. st.rerun() transitions between
  stages without recomputing prior work.
"""

import base64
import json
import os
import traceback
import uuid
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from pipeline import extract, ingest, score
from pipeline.agent.backends import get_backend
from pipeline.agent.graph import (
    assemble_output,
    build_graph,
    resume_after_classifier,
    resume_after_fields,
    start_graph,
)
from pipeline.agent.tracing import build_run_record, init_langsmith, log_run
from pipeline.constants import CLASSIFIER_CONFIDENCE_THRESHOLD
from pipeline.ingest import IngestionError
from pipeline.schemas import ExtractedFields, PipelineOutput, ProcessingMetadata

load_dotenv()
init_langsmith()

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Document Risk Extraction",
    page_icon="🔍",
    layout="wide",
)

st.title("Document Risk Extraction")
st.markdown("Upload a document to extract risk signals and assess fraud indicators.")

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

_SS_DEFAULTS: dict[str, Any] = {
    "stage": "idle",
    "mode": "single-model",
    "file_id": None,
    "image_b64": None,
    # classification outputs
    "classifier_category": None,
    "classifier_confidence": None,
    # analyst overrides (classifier checkpoint)
    "analyst_category": None,
    "analyst_confidence": None,
    # extraction outputs
    "extracted_fields_dict": None,
    "extraction_warnings": [],
    # analyst overrides (field-edit checkpoint)
    "analyst_fields": None,
    # multi-agent graph (preserved across reruns)
    "graph": None,
    # single-model full extraction result
    "extraction_result": None,
    # final assembled output + run log entry
    "output": None,
    "run_record": None,
}

for _k, _v in _SS_DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

ss = st.session_state

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CATEGORY_OPTIONS = [
    "chat_screenshot",
    "invoice",
    "marketplace_listing_screenshot",
    "website_screenshot",
    "other",
]

_LABEL_COLORS = {"low": "🟢", "medium": "🟡", "high": "🔴"}


def _render_results(output: PipelineOutput) -> None:
    """Render the two-column result display shared by both pipeline modes."""
    confidence_threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))
    if output.category_confidence < confidence_threshold:
        st.warning(
            "⚠️ Low confidence classification — results flagged for human review."
        )

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Extracted Fields")
        st.json(output.extracted_fields.model_dump())

    with col2:
        st.subheader("Risk Assessment")
        st.metric("Risk Score", f"{output.risk_score:.2f}")
        st.markdown(
            f"### {_LABEL_COLORS.get(output.risk_label, '')} "
            f"{output.risk_label.upper()} RISK"
        )
        st.markdown(f"**Summary:** {output.summary}")

        st.subheader("Scoring Rules")
        rules_data = [
            {
                "Rule ID": r.rule_id,
                "Triggered": "✓" if r.triggered else "✗",
                "Weight": f"{r.weight:.2f}",
                "Explanation": r.explanation if r.triggered else "-",
            }
            for r in output.scoring_rules
        ]
        st.dataframe(rules_data, use_container_width=True, hide_index=True)

    with st.expander("Processing Metadata"):
        st.json(
            {
                "file_id": output.file_id,
                "category": output.category,
                "category_confidence": output.category_confidence,
                "pipeline_mode": output.processing_metadata.pipeline_mode,
                "model_used": output.processing_metadata.model_used,
                "latency_ms": output.processing_metadata.latency_ms,
                "extraction_warnings": output.processing_metadata.extraction_warnings,
                "analyst_interventions": output.processing_metadata.analyst_interventions,
            }
        )

    if ss.run_record:
        with st.expander("Run Log (this run)"):
            st.json(ss.run_record)

    if output.processing_metadata.analyst_interventions:
        st.info(
            "ℹ️ Analyst interventions recorded: "
            + "; ".join(output.processing_metadata.analyst_interventions)
        )

    output_json = json.dumps(output.model_dump(), indent=2)
    st.download_button(
        label="Download Results (JSON)",
        data=output_json,
        file_name=f"risk_extraction_{output.file_id}.json",
        mime="application/json",
    )

    if st.button("🔄 Analyse another document"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


def _render_fields_form(fields: dict[str, Any]) -> None:
    """Render the editable fields form. On submit, sets analyst_fields and transitions."""
    st.subheader("Review Extracted Fields")
    st.markdown("Confirm or edit the extracted fields before scoring.")

    img_col, form_col = st.columns([1, 2])

    with img_col:
        st.markdown("**Original Document**")
        if ss.image_b64:
            st.image(base64.b64decode(ss.image_b64), use_container_width=True)

    with form_col:
        if ss.extraction_warnings:
            with st.expander("⚠️ Extraction warnings"):
                for w in ss.extraction_warnings:
                    st.markdown(f"- `{w}`")

        with st.form("fields_review_form"):
            col1, col2 = st.columns(2)
            with col1:
                entity_name = st.text_input(
                    "Entity name", value=fields.get("entity_name") or ""
                )
                amount_raw = st.text_input(
                    "Amount",
                    value=(
                        str(fields.get("amount"))
                        if fields.get("amount") is not None
                        else ""
                    ),
                )
                currency = st.text_input("Currency", value=fields.get("currency") or "")
                date = st.text_input("Date", value=fields.get("date") or "")
            with col2:
                counterparty = st.text_input(
                    "Counterparty", value=fields.get("counterparty") or ""
                )
                platform = st.text_input("Platform", value=fields.get("platform") or "")
                contact_details = st.text_input(
                    "Contact details", value=fields.get("contact_details") or ""
                )
                red_flags_raw = st.text_area(
                    "Red flags (one per line)",
                    value="\n".join(fields.get("red_flags") or []),
                    height=120,
                )
            submitted = st.form_submit_button("Continue →")

    if submitted:
        try:
            amount: float | None = float(amount_raw) if amount_raw.strip() else None
        except ValueError:
            amount = None

        ss.analyst_fields = {
            "entity_name": entity_name.strip() or None,
            "amount": amount,
            "currency": currency.strip() or None,
            "date": date.strip() or None,
            "counterparty": counterparty.strip() or None,
            "platform": platform.strip() or None,
            "contact_details": contact_details.strip() or None,
            "red_flags": [f.strip() for f in red_flags_raw.splitlines() if f.strip()],
        }
        ss.stage = "scoring"
        st.rerun()


# ---------------------------------------------------------------------------
# Stage: idle — mode selector + file uploader
# ---------------------------------------------------------------------------

if ss.stage == "idle":
    ss.mode = st.radio(
        "Pipeline mode",
        options=["single-model", "multi-agent"],
        horizontal=True,
        help=(
            "**single-model**: one LLM call classifies and extracts everything.  \n"
            "**multi-agent**: separate classifier and extractor nodes via LangGraph."
        ),
    )

    uploaded_file = st.file_uploader(
        "Upload a document",
        type=["pdf", "png", "jpg", "jpeg"],
        help="Supported formats: PDF, PNG, JPG, JPEG (max 10MB)",
    )

    if uploaded_file is not None:
        try:
            ingest.validate_file(uploaded_file)
            image_b64 = ingest.prepare_image(uploaded_file)
            ss.file_id = str(uuid.uuid4())
            ss.image_b64 = image_b64
            ss.stage = "classifying"
            st.rerun()
        except IngestionError as e:
            st.error(f"❌ {str(e)}")
        except Exception:
            st.error("❌ Unexpected error — please try again or contact support.")
            print(traceback.format_exc())

# ---------------------------------------------------------------------------
# Stage: classifying
# ---------------------------------------------------------------------------

elif ss.stage == "classifying":
    label = (
        "Classifying document…" if ss.mode == "multi-agent" else "Analysing document…"
    )
    with st.spinner(label):
        try:
            if ss.mode == "multi-agent":
                backend = get_backend()
                graph = build_graph(backend)
                ss.graph = graph
                graph_state = start_graph(
                    graph, file_id=ss.file_id, image_b64=ss.image_b64
                )
                ss.classifier_category = graph_state.get("classifier_category", "other")
                ss.classifier_confidence = float(
                    graph_state.get("classifier_confidence") or 0.0
                )
            else:
                # Single-model: full extraction in one call
                result = extract.extract(ss.image_b64)
                ss.extraction_result = result
                ss.classifier_category = result.category
                ss.classifier_confidence = result.category_confidence
                ss.extracted_fields_dict = result.extracted_fields.model_dump()
                ss.extraction_warnings = result.processing_metadata.extraction_warnings
        except Exception:
            st.error("❌ Unexpected error during analysis — please try again.")
            print(traceback.format_exc())
            ss.stage = "idle"
            st.rerun()

    if ss.classifier_confidence < CLASSIFIER_CONFIDENCE_THRESHOLD:
        ss.stage = "classifier_review"
    else:
        # Auto-confirm category, skip review form
        ss.analyst_category = ss.classifier_category
        ss.analyst_confidence = ss.classifier_confidence
        ss.stage = "extracting" if ss.mode == "multi-agent" else "fields_review"
    st.rerun()

# ---------------------------------------------------------------------------
# Stage: classifier_review
# ---------------------------------------------------------------------------

elif ss.stage == "classifier_review":
    st.warning(
        f"⚠️ Low confidence classification ({ss.classifier_confidence:.0%}) — "
        "please review and confirm or correct the document category before continuing."
    )

    current_idx = (
        _CATEGORY_OPTIONS.index(ss.classifier_category)
        if ss.classifier_category in _CATEGORY_OPTIONS
        else len(_CATEGORY_OPTIONS) - 1
    )

    img_col, form_col = st.columns([1, 2])

    with img_col:
        st.markdown("**Original Document**")
        if ss.image_b64:
            st.image(base64.b64decode(ss.image_b64), use_container_width=True)

    with form_col:
        with st.form("classifier_review_form"):
            st.subheader("Classifier Review")
            st.markdown(
                f"**Model output:** `{ss.classifier_category}` "
                f"(confidence: {ss.classifier_confidence:.0%})"
            )
            selected_category = st.selectbox(
                "Confirm or correct category",
                options=_CATEGORY_OPTIONS,
                index=current_idx,
            )
            confirmed_confidence = st.slider(
                "Adjusted confidence",
                min_value=0.0,
                max_value=1.0,
                value=ss.classifier_confidence,
                step=0.05,
            )
            submitted = st.form_submit_button("Continue →")

    if submitted:
        ss.analyst_category = selected_category
        ss.analyst_confidence = confirmed_confidence
        ss.stage = "extracting" if ss.mode == "multi-agent" else "fields_review"
        st.rerun()

# ---------------------------------------------------------------------------
# Stage: extracting (multi-agent only — single-model skips this stage)
# ---------------------------------------------------------------------------

elif ss.stage == "extracting":
    with st.spinner("Extracting document fields…"):
        try:
            graph_state = resume_after_classifier(
                ss.graph,
                file_id=ss.file_id,
                analyst_category=ss.analyst_category,
                analyst_confidence=ss.analyst_confidence,
            )
            ss.extracted_fields_dict = graph_state.get("extracted_fields") or {}
            ss.extraction_warnings = graph_state.get("extraction_warnings") or []
        except Exception:
            st.error("❌ Extraction failed — please try again.")
            print(traceback.format_exc())
            ss.stage = "idle"
            st.rerun()
    ss.stage = "fields_review"
    st.rerun()

# ---------------------------------------------------------------------------
# Stage: fields_review — always shown in both modes
# ---------------------------------------------------------------------------

elif ss.stage == "fields_review":
    _render_fields_form(ss.extracted_fields_dict or {})

# ---------------------------------------------------------------------------
# Stage: scoring
# ---------------------------------------------------------------------------

elif ss.stage == "scoring":
    with st.spinner("Scoring risk signals…"):
        analyst_fields: dict[str, Any] = ss.analyst_fields or {}

        try:
            if ss.mode == "multi-agent":
                final_state = resume_after_fields(
                    ss.graph,
                    file_id=ss.file_id,
                    analyst_fields=analyst_fields,
                )
                output = assemble_output(final_state, ss.file_id)
                timings: dict[str, int] = final_state.get("step_timings") or {}

            else:
                fields_obj = ExtractedFields(**analyst_fields)
                rule_results, risk_score, risk_label, summary = score.score(fields_obj)

                # Build analyst intervention audit trail for single-model
                analyst_interventions: list[str] = []
                if (
                    ss.analyst_category
                    and ss.analyst_category != ss.classifier_category
                ):
                    analyst_interventions.append(
                        f"category changed: {ss.classifier_category} → {ss.analyst_category}"
                    )
                orig_fields = ss.extracted_fields_dict or {}
                if analyst_fields != orig_fields:
                    analyst_interventions.append("extracted fields reviewed by analyst")

                er = ss.extraction_result
                output = PipelineOutput(
                    file_id=ss.file_id,
                    category=ss.analyst_category or ss.classifier_category,
                    category_confidence=(
                        ss.analyst_confidence
                        if ss.analyst_confidence is not None
                        else ss.classifier_confidence
                    ),
                    extracted_fields=fields_obj,
                    scoring_rules=rule_results,
                    risk_score=risk_score,
                    risk_label=risk_label,
                    summary=summary,
                    processing_metadata=ProcessingMetadata(
                        model_used=er.processing_metadata.model_used,
                        latency_ms=er.processing_metadata.latency_ms,
                        extraction_warnings=er.processing_metadata.extraction_warnings,
                        analyst_interventions=analyst_interventions,
                        pipeline_mode="single-model",
                    ),
                )
                timings = {"total": er.processing_metadata.latency_ms}

            ss.output = output

            run_record = build_run_record(
                file_id=ss.file_id,
                pipeline_mode=ss.mode,
                step_timings=timings,
                extraction_warnings=output.processing_metadata.extraction_warnings,
                analyst_interventions=output.processing_metadata.analyst_interventions,
                risk_label=output.risk_label,
                risk_score=output.risk_score,
            )
            log_run(run_record)
            ss.run_record = run_record

        except Exception:
            st.error("❌ Scoring failed — please try again.")
            print(traceback.format_exc())
            ss.stage = "idle"
            st.rerun()

    ss.stage = "complete"
    st.rerun()

# ---------------------------------------------------------------------------
# Stage: complete — results display
# ---------------------------------------------------------------------------

elif ss.stage == "complete":
    _render_results(ss.output)
