import json
import uuid
from pathlib import Path

import pytest
from pydantic_evals import Case, Dataset

from pipeline.extract import extract
from pipeline.ingest import prepare_image, validate_file
from pipeline.schemas import PipelineOutput
from pipeline.score import score
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


def run_pipeline(filename: str) -> dict:
    """
    Run the full pipeline on a golden file and return the PipelineOutput as a dict.
    """
    filepath = GOLDEN_DIR / filename
    file_id = str(uuid.uuid4())

    with open(filepath, "rb") as f:
        validate_file(f)
        f.seek(0)
        image_b64 = prepare_image(f)

    extraction_result = extract(image_b64)
    rule_results, risk_score, risk_label, summary = score(
        extraction_result.extracted_fields
    )

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
    return output.model_dump()


dataset = Dataset(
    cases=[
        Case(
            name="job_scam_chat_screenshot",
            inputs={"file": "chat_screenshot.png"},
            expected_output=load_expected("chat_screenshot"),
            evaluators=[
                JsonValid(),
                CategoryCorrect(),
                RiskLabelCorrect(),
                AmountCorrect(),
                CurrencyCorrect(),
                contact_details_judge,
                counterparty_judge,
                red_flags_judge,
            ],
        )
    ]
)


@pytest.mark.integration
def test_evals():
    """
    Runs the full pipeline on each golden document and evaluates outputs.
    """
    output = run_pipeline("chat_screenshot.png")
    report = dataset.evaluate_sync({"job_scam_chat_screenshot": output})
    report.print()

    for result in report.case_results:
        for eval_result in result.evaluator_results:
            assert eval_result.score == 1.0, (
                f"Eval '{eval_result.name}' failed " f"with score {eval_result.score}"
            )
