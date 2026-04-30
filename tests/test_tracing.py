"""Tests for tracing module: JSONL logging, LangSmith env guard."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from pipeline.agent.tracing import (
    build_run_record,
    init_langsmith,
    is_langsmith_enabled,
    log_run,
)

# ---------------------------------------------------------------------------
# is_langsmith_enabled
# ---------------------------------------------------------------------------


class TestIsLangsmithEnabled:
    def test_disabled_when_both_vars_absent(self):
        with patch.dict("os.environ", {}, clear=True):
            assert is_langsmith_enabled() is False

    def test_disabled_when_only_key_present(self):
        with patch.dict("os.environ", {"LANGSMITH_API_KEY": "key"}, clear=True):
            assert is_langsmith_enabled() is False

    def test_disabled_when_only_project_present(self):
        with patch.dict("os.environ", {"LANGSMITH_PROJECT": "proj"}, clear=True):
            assert is_langsmith_enabled() is False

    def test_enabled_when_both_vars_present(self):
        with patch.dict(
            "os.environ",
            {"LANGSMITH_API_KEY": "key", "LANGSMITH_PROJECT": "proj"},
        ):
            assert is_langsmith_enabled() is True


# ---------------------------------------------------------------------------
# init_langsmith
# ---------------------------------------------------------------------------


class TestInitLangsmith:
    def test_no_op_when_vars_absent(self):
        with patch.dict("os.environ", {}, clear=True):
            init_langsmith()  # must not raise
            assert "LANGCHAIN_TRACING_V2" not in os.environ

    def test_sets_langchain_vars_when_enabled(self):
        env = {"LANGSMITH_API_KEY": "mykey", "LANGSMITH_PROJECT": "myproject"}
        with patch.dict("os.environ", env):
            init_langsmith()
            assert os.environ.get("LANGCHAIN_TRACING_V2") == "true"
            assert os.environ.get("LANGCHAIN_API_KEY") == "mykey"
            assert os.environ.get("LANGCHAIN_PROJECT") == "myproject"


# ---------------------------------------------------------------------------
# log_run
# ---------------------------------------------------------------------------


class TestLogRun:
    def test_creates_file_and_writes_json(self, tmp_path):
        log_path = tmp_path / "runs.jsonl"
        with patch("pipeline.agent.tracing.RUN_LOG_PATH", str(log_path)):
            log_run({"test": "value", "n": 42})

        assert log_path.exists()
        line = log_path.read_text().strip()
        parsed = json.loads(line)
        assert parsed["test"] == "value"
        assert parsed["n"] == 42

    def test_appends_multiple_records(self, tmp_path):
        log_path = tmp_path / "runs.jsonl"
        with patch("pipeline.agent.tracing.RUN_LOG_PATH", str(log_path)):
            log_run({"run": 1})
            log_run({"run": 2})
            log_run({"run": 3})

        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 3
        records = [json.loads(l) for l in lines]
        assert [r["run"] for r in records] == [1, 2, 3]

    def test_creates_parent_directories(self, tmp_path):
        log_path = tmp_path / "deep" / "nested" / "runs.jsonl"
        with patch("pipeline.agent.tracing.RUN_LOG_PATH", str(log_path)):
            log_run({"x": 1})

        assert log_path.exists()

    def test_does_not_raise_on_unwritable_path(self):
        """log_run must never raise — it swallows write errors silently."""
        with patch(
            "pipeline.agent.tracing.RUN_LOG_PATH", "/proc/nonexistent/path.jsonl"
        ):
            log_run({"silent": "failure"})  # must not raise


# ---------------------------------------------------------------------------
# build_run_record
# ---------------------------------------------------------------------------


class TestBuildRunRecord:
    def _minimal(self, **overrides):
        defaults = dict(
            file_id="abc-123",
            pipeline_mode="single-model",
            step_timings={"total": 1500},
            extraction_warnings=[],
            analyst_interventions=[],
            risk_label="low",
            risk_score=0.1,
        )
        defaults.update(overrides)
        return build_run_record(**defaults)

    def test_contains_required_keys(self):
        record = self._minimal()
        for key in (
            "file_id",
            "pipeline_mode",
            "timestamp_utc",
            "step_timings_ms",
            "total_latency_ms",
            "extraction_warnings",
            "analyst_interventions",
            "risk_label",
            "risk_score",
            "cost_info",
            "langsmith_enabled",
        ):
            assert key in record, f"Missing key: {key}"

    def test_total_latency_is_sum_of_timings(self):
        record = self._minimal(step_timings={"a": 100, "b": 200, "c": 50})
        assert record["total_latency_ms"] == 350

    def test_cost_info_default_note_in_local_mode(self):
        record = self._minimal()
        assert "note" in record["cost_info"]
        assert "local" in record["cost_info"]["note"]

    def test_custom_cost_info_preserved(self):
        record = self._minimal(cost_info={"prompt_tokens": 500, "total_usd": 0.001})
        assert record["cost_info"]["prompt_tokens"] == 500

    def test_langsmith_run_url_defaults_none(self):
        record = self._minimal()
        assert record["langsmith_run_url"] is None

    def test_record_is_json_serialisable(self):
        record = self._minimal(
            step_timings={"classify": 300, "extract": 800},
            extraction_warnings=["amount: not returned by model"],
            analyst_interventions=["category changed: other → invoice"],
        )
        serialised = json.dumps(record)
        roundtrip = json.loads(serialised)
        assert roundtrip["file_id"] == "abc-123"
