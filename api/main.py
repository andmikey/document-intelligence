"""FastAPI application — replaces app.py (Streamlit).

The 6-stage Streamlit state machine collapses to three HTTP round-trips:

  POST /api/sessions
    → validate + prepare + classify (+ extract when mode/confidence allows)
    → returns stage: "classifier_review" | "fields_review"

  POST /api/sessions/{file_id}/confirm-category
    → stores analyst override; (multi-agent only) runs extractor
    → returns stage: "fields_review" + extracted_fields

  POST /api/sessions/{file_id}/confirm-fields
    → runs scorer, writes run log, assembles PipelineOutput
    → returns stage: "complete" + output

Session state lives in an in-memory dict keyed by file_id. It is ephemeral
(lost on server restart), which is acceptable for this single-user tool.
"""

from __future__ import annotations

import io
import json
import os
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from api import sessions
from api.models import (
    ConfirmCategoryRequest,
    ConfirmCategoryResponse,
    ConfirmFieldsRequest,
    ConfirmFieldsResponse,
    SessionResponse,
)
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
from pipeline.constants import CLASSIFIER_CONFIDENCE_THRESHOLD, RUN_LOG_PATH
from pipeline.ingest import IngestionError
from pipeline.schemas import ExtractedFields, PipelineOutput, ProcessingMetadata

load_dotenv()
init_langsmith()

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Document Risk Extraction API", version="0.1.0")

_cors_origins = os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# ---------------------------------------------------------------------------
# File adapter — bridges FastAPI UploadFile bytes → ingest module interface
# ---------------------------------------------------------------------------


class _FileAdapter:
    """Wraps raw bytes + filename to satisfy ingest.validate_file / prepare_image."""

    def __init__(self, data: bytes, filename: str) -> None:
        self._buf = io.BytesIO(data)
        self.name = filename

    def read(self, size: int = -1) -> bytes:
        return self._buf.read() if size == -1 else self._buf.read(size)

    def seek(self, pos: int, whence: int = 0) -> int:
        return self._buf.seek(pos, whence)

    def tell(self) -> int:
        return self._buf.tell()


# ---------------------------------------------------------------------------
# POST /api/sessions — upload + classify (+ optional extract)
# ---------------------------------------------------------------------------


@app.post("/api/sessions", response_model=SessionResponse)
async def create_session(
    file: UploadFile,
    mode: str = Form(...),
) -> SessionResponse:
    if mode not in ("single-model", "multi-agent"):
        raise HTTPException(422, detail="mode must be 'single-model' or 'multi-agent'")

    data = await file.read()
    adapter = _FileAdapter(data, file.filename or "upload")

    # Validate
    try:
        await run_in_threadpool(ingest.validate_file, adapter)
    except IngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Prepare image (CPU-bound — run in threadpool)
    adapter.seek(0)
    image_b64: str = await run_in_threadpool(ingest.prepare_image, adapter)

    file_id = str(uuid.uuid4())

    # ----- single-model: one combined classify + extract call -----
    if mode == "single-model":
        result = await run_in_threadpool(extract.extract, image_b64)

        session = sessions.SessionState(
            mode=mode,
            image_b64=image_b64,
            classifier_category=result.category,
            classifier_confidence=result.category_confidence,
            extracted_fields=result.extracted_fields.model_dump(),
            extraction_warnings=result.processing_metadata.extraction_warnings,
            extraction_result=result,
        )

        if result.category_confidence < CLASSIFIER_CONFIDENCE_THRESHOLD:
            stage: str = "classifier_review"
        else:
            session.analyst_category = result.category
            session.analyst_confidence = result.category_confidence
            stage = "fields_review"

        sessions.create(file_id, session)

        return SessionResponse(
            file_id=file_id,
            stage=stage,  # type: ignore[arg-type]
            classifier_category=result.category,
            classifier_confidence=result.category_confidence,
            extracted_fields=session.extracted_fields,
            extraction_warnings=session.extraction_warnings,
            image_b64=image_b64,
        )

    # ----- multi-agent: separate classify and extract nodes -----
    backend = await run_in_threadpool(get_backend)
    graph = await run_in_threadpool(build_graph, backend)
    graph_state: dict[str, Any] = await run_in_threadpool(
        start_graph, graph, file_id=file_id, image_b64=image_b64
    )

    classifier_category: str = graph_state.get("classifier_category") or "other"
    classifier_confidence: float = float(
        graph_state.get("classifier_confidence") or 0.0
    )

    session = sessions.SessionState(
        mode=mode,
        image_b64=image_b64,
        classifier_category=classifier_category,
        classifier_confidence=classifier_confidence,
        graph=graph,
    )

    if classifier_confidence < CLASSIFIER_CONFIDENCE_THRESHOLD:
        # Low confidence — frontend must show classifier_review form
        sessions.create(file_id, session)
        return SessionResponse(
            file_id=file_id,
            stage="classifier_review",
            classifier_category=classifier_category,
            classifier_confidence=classifier_confidence,
            image_b64=image_b64,
        )

    # High confidence — auto-confirm and run extractor immediately
    session.analyst_category = classifier_category
    session.analyst_confidence = classifier_confidence
    sessions.create(file_id, session)

    graph_state = await run_in_threadpool(
        resume_after_classifier,
        graph,
        file_id=file_id,
        analyst_category=classifier_category,
        analyst_confidence=classifier_confidence,
    )
    extracted_fields: dict[str, Any] = graph_state.get("extracted_fields") or {}
    extraction_warnings: list[str] = graph_state.get("extraction_warnings") or []
    session.extracted_fields = extracted_fields
    session.extraction_warnings = extraction_warnings

    return SessionResponse(
        file_id=file_id,
        stage="fields_review",
        classifier_category=classifier_category,
        classifier_confidence=classifier_confidence,
        extracted_fields=extracted_fields,
        extraction_warnings=extraction_warnings,
        image_b64=image_b64,
    )


# ---------------------------------------------------------------------------
# POST /api/sessions/{file_id}/confirm-category
# ---------------------------------------------------------------------------


@app.post(
    "/api/sessions/{file_id}/confirm-category",
    response_model=ConfirmCategoryResponse,
)
async def confirm_category(
    file_id: str,
    body: ConfirmCategoryRequest,
) -> ConfirmCategoryResponse:
    session = sessions.get(file_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    session.analyst_category = body.category
    session.analyst_confidence = body.confidence

    if session.mode == "multi-agent":
        graph_state: dict[str, Any] = await run_in_threadpool(
            resume_after_classifier,
            session.graph,
            file_id=file_id,
            analyst_category=body.category,
            analyst_confidence=body.confidence,
        )
        extracted_fields: dict[str, Any] = graph_state.get("extracted_fields") or {}
        extraction_warnings: list[str] = graph_state.get("extraction_warnings") or []
        session.extracted_fields = extracted_fields
        session.extraction_warnings = extraction_warnings
    else:
        # Single-model: extraction already ran; analyst can only override category
        extracted_fields = session.extracted_fields or {}
        extraction_warnings = session.extraction_warnings

    return ConfirmCategoryResponse(
        extracted_fields=extracted_fields,
        extraction_warnings=extraction_warnings,
    )


# ---------------------------------------------------------------------------
# POST /api/sessions/{file_id}/confirm-fields
# ---------------------------------------------------------------------------


@app.post(
    "/api/sessions/{file_id}/confirm-fields",
    response_model=ConfirmFieldsResponse,
)
async def confirm_fields(
    file_id: str,
    body: ConfirmFieldsRequest,
) -> ConfirmFieldsResponse:
    session = sessions.get(file_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    analyst_fields = body.fields.model_dump()

    if session.mode == "multi-agent":
        final_state: dict[str, Any] = await run_in_threadpool(
            resume_after_fields,
            session.graph,
            file_id=file_id,
            analyst_fields=analyst_fields,
        )
        output: PipelineOutput = assemble_output(final_state, file_id)
        timings: dict[str, int] = final_state.get("step_timings") or {}

    else:
        # Single-model: run scorer manually, then assemble PipelineOutput
        fields_obj = ExtractedFields(**analyst_fields)
        rule_results, risk_score, risk_label, summary = await run_in_threadpool(
            score.score, fields_obj
        )

        analyst_interventions: list[str] = []
        if (
            session.analyst_category
            and session.analyst_category != session.classifier_category
        ):
            analyst_interventions.append(
                f"category changed: {session.classifier_category} → {session.analyst_category}"
            )
        orig_fields = session.extracted_fields or {}
        if analyst_fields != orig_fields:
            analyst_interventions.append("extracted fields reviewed by analyst")

        er = session.extraction_result
        output = PipelineOutput(
            file_id=file_id,
            category=session.analyst_category or session.classifier_category,
            category_confidence=(
                session.analyst_confidence
                if session.analyst_confidence is not None
                else session.classifier_confidence
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

    run_record = build_run_record(
        file_id=file_id,
        pipeline_mode=session.mode,
        step_timings=timings,
        extraction_warnings=output.processing_metadata.extraction_warnings,
        analyst_interventions=output.processing_metadata.analyst_interventions,
        risk_label=output.risk_label,
        risk_score=output.risk_score,
    )
    log_run(run_record)

    return ConfirmFieldsResponse(output=output)


# ---------------------------------------------------------------------------
# GET /api/logs
# ---------------------------------------------------------------------------


@app.get("/api/logs")
async def get_logs() -> list[dict[str, Any]]:
    log_path = Path(RUN_LOG_PATH)
    if not log_path.exists():
        return []
    records: list[dict[str, Any]] = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records
