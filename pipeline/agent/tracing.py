"""Optional LangSmith tracing initialisation and local JSONL run logging.

LangSmith is completely optional. When LANGSMITH_API_KEY and LANGSMITH_PROJECT
are absent from the environment, all tracing calls are silent no-ops and the
app runs identically without remote observability.

Local run logging (logs/pipeline_runs.jsonl) always runs regardless of
LangSmith configuration, using a best-effort append that never raises.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pipeline.constants import RUN_LOG_PATH

# ---------------------------------------------------------------------------
# LangSmith
# ---------------------------------------------------------------------------


def is_langsmith_enabled() -> bool:
    """Return True only when both required LangSmith env vars are present."""
    return bool(os.getenv("LANGSMITH_API_KEY")) and bool(os.getenv("LANGSMITH_PROJECT"))


def init_langsmith() -> None:
    """Initialise LangSmith tracing if env vars are present. Silent no-op otherwise.

    LangChain picks up tracing automatically once these env vars are set, so
    all LangChain/LangGraph calls will be traced without further instrumentation.
    """
    if not is_langsmith_enabled():
        return
    # LangChain reads LANGCHAIN_* vars to enable remote tracing
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = os.environ["LANGSMITH_API_KEY"]
    os.environ["LANGCHAIN_PROJECT"] = os.environ["LANGSMITH_PROJECT"]


# ---------------------------------------------------------------------------
# Local JSONL run logger
# ---------------------------------------------------------------------------


def log_run(record: dict[str, Any]) -> None:
    """Append one JSON line to the local run log. Silently skips on any error.

    The log file is created (with parent dirs) if it does not exist.
    Failure to write never propagates — observability must not break the app.
    """
    try:
        log_path = Path(RUN_LOG_PATH)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception:
        pass


def build_run_record(
    *,
    file_id: str,
    pipeline_mode: str,
    step_timings: dict[str, int],
    extraction_warnings: list[str],
    analyst_interventions: list[str],
    risk_label: str,
    risk_score: float,
    langsmith_run_url: Optional[str] = None,
    trace_id: Optional[str] = None,
    cost_info: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build the structured dict written to the JSONL log and shown in the UI.

    cost_info is always present; in local/offline mode it carries a note
    field rather than actual token costs so the dashboard schema stays stable.
    """
    return {
        "file_id": file_id,
        "pipeline_mode": pipeline_mode,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "step_timings_ms": step_timings,
        "total_latency_ms": sum(step_timings.values()),
        "extraction_warnings": extraction_warnings,
        "analyst_interventions": analyst_interventions,
        "risk_label": risk_label,
        "risk_score": risk_score,
        "langsmith_run_url": langsmith_run_url,
        "trace_id": trace_id,
        "cost_info": cost_info or {"note": "not_available_in_local_mode"},
        "langsmith_enabled": is_langsmith_enabled(),
    }
