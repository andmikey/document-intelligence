import json
import uuid
from pathlib import Path

import pytest
from pydantic_evals import Case, Dataset

from pipeline.agent.graph import assemble_output, build_graph
from pipeline.ingest import prepare_image, validate_file
from tests.evals.evals import (
    AmountCorrect,
    CategoryCorrect,
    CurrencyCorrect,
    JsonValid,
    RiskLabelCorrect,
    contact_details_judge,
    counterparty_judge,
    red_flags_judge,
)

GOLDEN_DIR = Path(__file__).parent / "golden_set"


def load_expected(name: str) -> dict:
    with open(GOLDEN_DIR / f"{name}_expected.json") as f:
        return json.load(f)


def run_pipeline(inputs: dict) -> dict:
    """
    Run the full pipeline on a golden file and return the PipelineOutput as a dict.
    """
    filepath = GOLDEN_DIR / inputs["file"]
    file_id = str(uuid.uuid4())

    with open(filepath, "rb") as f:
        validate_file(f)
        f.seek(0)
        image_b64 = prepare_image(f)

    graph = build_graph(headless=True)
    initial = {
        "file_id": file_id,
        "image_b64": image_b64,
        "pipeline_mode": "multi-agent",
        "step_timings": {},
        "error": None,
        "trace_id": None,
        "langsmith_run_url": None,
    }
    state = graph.invoke(initial, config={"configurable": {"thread_id": file_id}})
    output = assemble_output(state, file_id)
    return output.model_dump()


dataset = Dataset(
    cases=[
        Case(
            name="job_scam_chat_screenshot",
            inputs={"file": "chat_screenshot.png"},
            expected_output=load_expected("chat_screenshot"),
            evaluators=(
                JsonValid(),
                CategoryCorrect(),
                RiskLabelCorrect(),
                AmountCorrect(),
                CurrencyCorrect(),
                contact_details_judge,
                counterparty_judge,
                red_flags_judge,
            ),
        )
    ]
)


@pytest.mark.integration
def test_evals():
    """
    Runs the full pipeline on each golden document and evaluates outputs.
    """
    report = dataset.evaluate_sync(run_pipeline, progress=False)
    report.print()

    for case in report.cases:
        for name, result in case.scores.items():
            assert (
                result.value == 1.0
            ), f"Score eval '{name}' failed with score {result.value}"
        for name, result in case.assertions.items():
            assert result.value is True, f"Assertion eval '{name}' failed" + (
                f": {result.reason}" if result.reason else ""
            )
