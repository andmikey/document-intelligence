"""Streamlit UI for document risk extraction."""

import json
import os
import traceback
import uuid

import streamlit as st
from dotenv import load_dotenv

from pipeline import extract, ingest, score
from pipeline.ingest import IngestionError
from pipeline.schemas import PipelineOutput

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Document Risk Extraction",
    page_icon="🔍",
    layout="wide",
)

# Title and description
st.title("Document Risk Extraction")
st.markdown("Upload a document to extract risk signals and assess fraud indicators.")

# File uploader
uploaded_file = st.file_uploader(
    "Upload a document",
    type=["pdf", "png", "jpg", "jpeg"],
    help="Supported formats: PDF, PNG, JPG, JPEG (max 10MB)",
)

if uploaded_file is not None:
    # Generate file ID at upload time
    file_id = str(uuid.uuid4())

    try:
        with st.spinner("Processing document..."):
            # Step 1: Validate file
            ingest.validate_file(uploaded_file)

            # Step 2: Prepare image
            image_b64 = ingest.prepare_image(uploaded_file)

            # Step 3: Extract fields
            extraction_result = extract.extract(image_b64)

            # Step 4: Score risk
            rule_results, risk_score, risk_label, summary = score.score(
                extraction_result.extracted_fields
            )

            # Step 5: Assemble output
            output = PipelineOutput(
                file_id=file_id,
                category=extraction_result.category,
                category_confidence=extraction_result.category_confidence,
                extracted_fields=extraction_result.extracted_fields,
                scoring_rules=rule_results,
                risk_score=risk_score,
                risk_label=risk_label,
                summary=summary,
                processing_metadata=extraction_result.processing_metadata,
            )

        # Check confidence threshold
        confidence_threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))
        if output.category_confidence < confidence_threshold:
            st.warning(
                "⚠️ Low confidence classification — results flagged for human review."
            )

        # Display results in two columns
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Extracted Fields")
            # Display as JSON
            st.json(output.extracted_fields.model_dump())

        with col2:
            st.subheader("Risk Assessment")

            # Risk score (large text)
            st.metric("Risk Score", f"{output.risk_score:.2f}")

            # Risk label as colored badge
            label_colors = {
                "low": "🟢",
                "medium": "🟡",
                "high": "🔴",
            }
            st.markdown(
                f"### {label_colors.get(output.risk_label, '')} {output.risk_label.upper()} RISK"
            )

            # Human-readable summary
            st.markdown(f"**Summary:** {output.summary}")

            # Rules table
            st.subheader("Scoring Rules")

            # Convert rules to table format
            rules_data = []
            for rule in output.scoring_rules:
                rules_data.append(
                    {
                        "Rule ID": rule.rule_id,
                        "Triggered": "✓" if rule.triggered else "✗",
                        "Weight": f"{rule.weight:.2f}",
                        "Explanation": rule.explanation if rule.triggered else "-",
                    }
                )

            st.dataframe(
                rules_data,
                use_container_width=True,
                hide_index=True,
            )

        # Display metadata in expander
        with st.expander("Processing Metadata"):
            st.json(
                {
                    "file_id": output.file_id,
                    "category": output.category,
                    "category_confidence": output.category_confidence,
                    "model_used": output.processing_metadata.model_used,
                    "latency_ms": output.processing_metadata.latency_ms,
                    "extraction_warnings": output.processing_metadata.extraction_warnings,
                }
            )

        # Download button for full output
        output_json = json.dumps(output.model_dump(), indent=2)
        st.download_button(
            label="Download Results (JSON)",
            data=output_json,
            file_name=f"risk_extraction_{file_id}.json",
            mime="application/json",
        )

    except IngestionError as e:
        # User-friendly error for ingestion failures
        st.error(f"❌ {str(e)}")

    except Exception as e:
        # Generic error handler
        st.error("❌ Unexpected error — please try again or contact support.")
        # Log traceback server-side
        print("Error processing document:")
        print(traceback.format_exc())
