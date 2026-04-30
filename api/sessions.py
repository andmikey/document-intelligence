"""In-memory session store for the FastAPI pipeline.

Sessions are keyed by file_id (UUID). State is ephemeral — lost on server
restart. A Redis-backed store is the natural upgrade path for persistence.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SessionState:
    mode: str  # "single-model" | "multi-agent"
    image_b64: str

    # Classifier outputs
    classifier_category: str = ""
    classifier_confidence: float = 0.0

    # Analyst overrides (written by confirm-category endpoint)
    analyst_category: Optional[str] = None
    analyst_confidence: Optional[float] = None

    # Extraction results
    extracted_fields: Optional[dict[str, Any]] = None
    extraction_warnings: list[str] = field(default_factory=list)

    # Single-model only: the full ExtractionResult (needed for scoring metadata)
    extraction_result: Optional[Any] = None

    # Multi-agent only: compiled LangGraph graph (holds MemorySaver state inside)
    graph: Optional[Any] = None


_store: dict[str, SessionState] = {}
_lock = threading.Lock()


def create(file_id: str, state: SessionState) -> None:
    with _lock:
        _store[file_id] = state


def get(file_id: str) -> Optional[SessionState]:
    with _lock:
        return _store.get(file_id)


def delete(file_id: str) -> None:
    with _lock:
        _store.pop(file_id, None)
