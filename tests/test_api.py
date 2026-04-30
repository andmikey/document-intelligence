"""Integration tests for the FastAPI pipeline endpoints.

Uses FastAPI's TestClient (ASGI transport — no real sockets) so the
conftest.py network guard does not interfere. LOCAL_DEV_MODE=true means
the LocalFixtureBackend is used for all LLM calls.
"""

from __future__ import annotations

import io
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image

# Ensure offline mode before importing the app
os.environ.setdefault("LOCAL_DEV_MODE", "true")
os.environ.setdefault("ALLOW_NETWORK_CALLS", "false")

from api.main import app  # noqa: E402

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_png_bytes(width: int = 20, height: int = 20) -> bytes:
    img = Image.new("RGB", (width, height), color=(120, 160, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _upload(png_bytes: bytes, mode: str = "single-model"):
    return client.post(
        "/api/sessions",
        files={"file": ("test.png", png_bytes, "image/png")},
        data={"mode": mode},
    )


def _reach_fields_review(png_bytes: bytes, mode: str = "single-model") -> str:
    """Upload a file and advance past classifier_review if needed. Returns file_id."""
    res = _upload(png_bytes, mode)
    assert res.status_code == 200
    data = res.json()
    file_id = data["file_id"]

    if data["stage"] == "classifier_review":
        confirm = client.post(
            f"/api/sessions/{file_id}/confirm-category",
            json={"category": data["classifier_category"], "confidence": 0.9},
        )
        assert confirm.status_code == 200

    return file_id


_EMPTY_FIELDS = {
    "entity_name": None,
    "amount": None,
    "currency": None,
    "date": None,
    "counterparty": None,
    "platform": None,
    "contact_details": None,
    "red_flags": [],
}

# ---------------------------------------------------------------------------
# POST /api/sessions
# ---------------------------------------------------------------------------


class TestCreateSession:
    def test_single_model_happy_path(self):
        res = _upload(_make_png_bytes(), "single-model")
        assert res.status_code == 200
        body = res.json()
        assert "file_id" in body
        assert body["stage"] in ("classifier_review", "fields_review")
        assert "classifier_category" in body
        assert isinstance(body["classifier_confidence"], float)
        assert "image_b64" in body
        assert body["image_b64"]  # non-empty

    def test_multi_agent_happy_path(self):
        res = _upload(_make_png_bytes(), "multi-agent")
        assert res.status_code == 200
        body = res.json()
        assert "file_id" in body
        assert body["stage"] in ("classifier_review", "fields_review")

    def test_fields_review_stage_includes_extracted_fields(self):
        """When stage is fields_review the response must include extracted_fields."""
        png = _make_png_bytes()
        res = _upload(png, "single-model")
        assert res.status_code == 200
        body = res.json()
        if body["stage"] == "fields_review":
            assert body["extracted_fields"] is not None

    def test_invalid_file_type_returns_422(self):
        res = client.post(
            "/api/sessions",
            files={"file": ("test.txt", b"not an image", "text/plain")},
            data={"mode": "single-model"},
        )
        assert res.status_code == 422

    def test_invalid_mode_returns_422(self):
        res = client.post(
            "/api/sessions",
            files={"file": ("test.png", _make_png_bytes(), "image/png")},
            data={"mode": "bad-mode"},
        )
        assert res.status_code == 422

    def test_missing_mode_returns_422(self):
        res = client.post(
            "/api/sessions",
            files={"file": ("test.png", _make_png_bytes(), "image/png")},
        )
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/sessions/{file_id}/confirm-category
# ---------------------------------------------------------------------------


class TestConfirmCategory:
    def test_returns_fields_review_with_extracted_fields(self):
        png = _make_png_bytes()
        create_res = _upload(png, "single-model")
        assert create_res.status_code == 200
        data = create_res.json()
        file_id = data["file_id"]

        res = client.post(
            f"/api/sessions/{file_id}/confirm-category",
            json={"category": "invoice", "confidence": 0.95},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["stage"] == "fields_review"
        assert "extracted_fields" in body
        assert isinstance(body["extraction_warnings"], list)

    def test_unknown_session_returns_404(self):
        res = client.post(
            f"/api/sessions/{uuid.uuid4()}/confirm-category",
            json={"category": "invoice", "confidence": 0.9},
        )
        assert res.status_code == 404

    def test_invalid_confidence_returns_422(self):
        png = _make_png_bytes()
        create_res = _upload(png, "single-model")
        file_id = create_res.json()["file_id"]

        res = client.post(
            f"/api/sessions/{file_id}/confirm-category",
            json={"category": "invoice", "confidence": 1.5},  # out of range
        )
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/sessions/{file_id}/confirm-fields
# ---------------------------------------------------------------------------


class TestConfirmFields:
    def test_returns_complete_with_output(self):
        file_id = _reach_fields_review(_make_png_bytes(), "single-model")

        res = client.post(
            f"/api/sessions/{file_id}/confirm-fields",
            json={"fields": _EMPTY_FIELDS},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["stage"] == "complete"
        output = body["output"]
        assert "risk_score" in output
        assert "risk_label" in output
        assert output["risk_label"] in ("low", "medium", "high")
        assert "scoring_rules" in output
        assert isinstance(output["scoring_rules"], list)

    def test_output_contains_file_id(self):
        file_id = _reach_fields_review(_make_png_bytes(), "single-model")

        res = client.post(
            f"/api/sessions/{file_id}/confirm-fields",
            json={"fields": _EMPTY_FIELDS},
        )
        assert res.status_code == 200
        assert res.json()["output"]["file_id"] == file_id

    def test_multi_agent_end_to_end(self):
        file_id = _reach_fields_review(_make_png_bytes(), "multi-agent")

        res = client.post(
            f"/api/sessions/{file_id}/confirm-fields",
            json={"fields": _EMPTY_FIELDS},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["stage"] == "complete"
        assert body["output"]["processing_metadata"]["pipeline_mode"] == "multi-agent"

    def test_unknown_session_returns_404(self):
        res = client.post(
            f"/api/sessions/{uuid.uuid4()}/confirm-fields",
            json={"fields": _EMPTY_FIELDS},
        )
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/logs
# ---------------------------------------------------------------------------


class TestGetLogs:
    def test_returns_list(self):
        res = client.get("/api/logs")
        assert res.status_code == 200
        assert isinstance(res.json(), list)
