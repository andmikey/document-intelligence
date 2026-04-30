"""Configuration constants for the pipeline."""

import os

# LLM model configuration
LLM_MODEL_NAME = "google/gemini-2.0-flash-001"

# Risk scoring thresholds
RISK_THRESHOLD_LOW_MEDIUM = 0.35  # Threshold between low and medium risk
RISK_THRESHOLD_MEDIUM_HIGH = 0.65  # Threshold between medium and high risk

# Multi-agent / HITL configuration
# Confidence below this triggers a classifier review checkpoint in the UI.
CLASSIFIER_CONFIDENCE_THRESHOLD = float(
    os.getenv("CLASSIFIER_CONFIDENCE_THRESHOLD", "0.6")
)

# Development posture
# Set LOCAL_DEV_MODE=true to use offline fixture-based LLM stubs.
# ALLOW_NETWORK_CALLS=false (default in local mode) causes tests to fail fast
# if any real HTTP call is attempted.
LOCAL_DEV_MODE: bool = os.getenv("LOCAL_DEV_MODE", "true").lower() == "true"
ALLOW_NETWORK_CALLS: bool = os.getenv("ALLOW_NETWORK_CALLS", "false").lower() == "true"

# Local observability
RUN_LOG_PATH = os.getenv("RUN_LOG_PATH", "logs/pipeline_runs.jsonl")
