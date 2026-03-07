# Implementation Spec: Document Intelligence Pipeline

## Tooling decisions

| Concern | Tool | Rationale |
|---|---|---|
| UI | Streamlit | Minimal boilerplate, file upload and side-by-side layout built in. No separate API server needed for a single-analyst prototype. |
| LLM calls | OpenRouter via `openai` Python SDK | OpenRouter is OpenAI-API-compatible; swap `base_url` and `api_key`, no custom HTTP client needed |
| Model | `google/gemini-2.0-flash-001` | Strong vision capability for screenshots, fast, cheap, supports JSON mode via OpenRouter |
| Output validation | Pydantic v2 | Schema enforcement, null-filling, and `extraction_warnings` generation in one step. Use `model_config = ConfigDict(extra='ignore')` on all models so unexpected LLM output fields don't cause validation failures. |
| PDF handling | `pymupdf` (fitz) | Converts PDF pages to images for the VLM; handles corrupt file detection |
| Image handling | Pillow | Resize/compress before sending to API to reduce latency and cost |
| Environment config | `python-dotenv` | API key and tuneable parameters loaded from `.env` |
| Testing | `pytest` | Unit tests for rules, ingest validation, scoring aggregation, and extraction parsing |

---

## Repository structure

```
/
├── app.py                  # Streamlit UI entry point
├── pipeline/
│   ├── __init__.py
│   ├── ingest.py           # File validation and preprocessing
│   ├── extract.py          # LLM call, prompt, output parsing
│   ├── schemas.py          # Pydantic models for all inputs/outputs
│   ├── score.py            # Rule registry and scoring aggregation
│   └── rules/
│       ├── __init__.py     # Rule registry — only file to edit when adding a rule
│       ├── base.py         # BaseRule abstract class
│       └── advance_fee.py  # Concrete rule implementations
├── tests/
│   ├── test_rules.py       # One trigger/no-trigger test per rule
│   ├── test_ingest.py      # File validation and image prep tests
│   ├── test_score.py       # Aggregation and label threshold tests
│   └── test_extract.py     # Extraction parsing tests (mocked LLM responses)
├── examples/
│   ├── chat_screenshot.png
│   └── example_output.json
├── .env.example
├── requirements.txt
└── README.md
```

---

## Module specifications

### `pipeline/schemas.py`

Define all Pydantic models here. Nothing else. All optional fields must default to
`None`; `red_flags` must default to `[]`. This ensures Pydantic partial validation
works correctly when the LLM omits fields.

```python
# ExtractedFields — output of the LLM extraction step
class ExtractedFields(BaseModel):
    model_config = ConfigDict(extra='ignore')

    entity_name: str | None = None
    amount: float | None = None
    currency: str | None = None
    date: str | None = None
    counterparty: str | None = None
    platform: str | None = None
    contact_details: str | None = None
    compensation_type: str | None = None     # e.g. "USDT", "GBP", "unspecified"
    job_description: str | None = None
    referral_code_present: bool | None = None
    third_party_recruiter_mentioned: bool | None = None
    platform_migration_requested: bool | None = None
    red_flags: list[str] = []               # descriptive labels, not risk judgements

# ProcessingMetadata — populated from ExtractionResult, included in final output
class ProcessingMetadata(BaseModel):
    model_used: str
    latency_ms: int
    extraction_warnings: list[str]          # missing fields, parse issues, etc.

# ExtractionResult — internal result of the extraction step, not the final output
class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra='ignore')

    category: Literal["invoice", "marketplace_listing_screenshot",
                       "chat_screenshot", "website_screenshot", "other"]
    category_confidence: float
    extracted_fields: ExtractedFields
    processing_metadata: ProcessingMetadata

# RuleResult — output of a single scoring rule
class RuleResult(BaseModel):
    rule_id: str
    triggered: bool
    weight: float
    explanation: str

# PipelineOutput — the final output contract returned to the UI and saved as JSON
class PipelineOutput(BaseModel):
    file_id: str
    category: str
    category_confidence: float
    extracted_fields: ExtractedFields
    scoring_rules: list[RuleResult]
    risk_score: float
    risk_label: Literal["low", "medium", "high"]
    summary: str
    processing_metadata: ProcessingMetadata
```

Note: `extraction_warnings` lives inside `processing_metadata` in both
`ExtractionResult` and `PipelineOutput`, matching the output contract in the spec exactly.

---

### `pipeline/ingest.py`

Responsibilities: validate the uploaded file, convert to a base64-encoded image
ready for the LLM. All errors raise a custom `IngestionError` with a human-readable
message; the UI catches this and displays it without a traceback.

```
validate_file(file) -> None | raises IngestionError
    - Check extension is in {pdf, png, jpg, jpeg}; raise on unsupported type
    - Check file size <= MAX_FILE_SIZE_MB (default 10, from env); raise if exceeded
    - For PDFs: attempt to open with pymupdf; raise IngestionError on corrupt file
    - For images: attempt to open with Pillow; raise IngestionError on corrupt file

prepare_image(file) -> str  (base64 encoded JPEG)
    - PDFs: render first page to image via pymupdf at 150dpi
    - Images: resize to max 1568px on longest side (Gemini recommended max)
    - Convert to JPEG, base64 encode
    - Return base64 string
    - Note: resizing before the API call is the primary latency optimisation
```

---

### `pipeline/extract.py`

Responsibilities: call the LLM, parse the response, validate against schema,
return `ExtractionResult`.

**Prompt structure:**

```
SYSTEM:
You are a document analysis assistant for a financial fraud investigation team.
Your job is to observe and describe document contents accurately.
Do not make fraud judgements — only extract factual attributes and surface observable signals.
Always respond with valid JSON matching the schema below. Use null for fields not present.

[Full JSON schema with field descriptions]

USER:
Analyse this document. Extract all fields.

For the category field, choose from: invoice, marketplace_listing_screenshot,
chat_screenshot, website_screenshot, other.

For red_flags, return a list of short descriptive labels for any observable signals
present in the document. Examples of valid labels (not exhaustive — include any
additional signals you observe):
  "cryptocurrency_compensation_mentioned"
  "third_party_recruiter_referenced"
  "platform_migration_requested"
  "referral_code_present"
  "unknown_contact_initiated"
  "urgency_language_present"
  "secrecy_instruction_present"
  "unverifiable_employer"
Do not use evaluative language like "suspicious" or "fraudulent" in red_flags.

For category_confidence, return a float 0-1 representing your confidence in the
category assignment. Note: this is your self-assessed confidence, not a calibrated
probability.

[base64 image]
```

**Function signatures:**

```
call_llm(image_b64: str) -> tuple[dict, str, int]
    - POST to OpenRouter with temperature=0, response_format={"type": "json_object"}
    - Model: google/gemini-2.0-flash-001
    - Record start timestamp before call, compute latency_ms after
    - Return (parsed response dict, model name, latency_ms)
    - On timeout or non-200: wait 2s and retry once
    - On second failure: raise LLMCallError with failure mode description

parse_extraction(raw: dict, model: str, latency_ms: int) -> ExtractionResult
    - Attempt Pydantic validation of raw dict against ExtractionResult schema
    - On ValidationError: collect names of invalid/missing fields, fill with null,
      append field names to extraction_warnings, return partial result
    - On complete parse failure (raw is not a dict): raise ExtractionParseError
      with raw response logged for debugging

extract(image_b64: str) -> ExtractionResult
    - Orchestrates call_llm -> parse_extraction
    - Catches LLMCallError: returns ExtractionResult with all fields null,
      category="other", category_confidence=0.0,
      extraction_warnings=["LLM call failed: <reason>"]
    - Catches ExtractionParseError: returns ExtractionResult with all fields null,
      extraction_warnings=["Extraction parse failed — raw output logged"]
```

**On LLM non-determinism:** temperature=0 is the primary mechanism for consistency.
JSON mode enforces output structure. A single retry handles transient failures.
This trades a small risk of identical errors on retry for implementation simplicity
appropriate to a prototype.

---

### `pipeline/rules/base.py`

```python
from abc import ABC, abstractmethod
from pipeline.schemas import ExtractedFields, RuleResult

class BaseRule(ABC):
    rule_id: str       # unique snake_case identifier
    weight: float      # contribution to risk score if triggered (0-1)
    bucket: str        # thematic group for capped aggregation

    @abstractmethod
    def evaluate(self, fields: ExtractedFields) -> RuleResult:
        """
        Evaluate the rule against extracted fields.
        Must return a RuleResult regardless of outcome.
        Must not raise exceptions — catch internally and return
        triggered=False with an explanation if something goes wrong.
        """
        ...
```

**Adding a new rule:** create a class in the appropriate file (or a new file for a
new typology) inheriting `BaseRule`, implement `evaluate()`, then add an instance
to `RULES` in `pipeline/rules/__init__.py`. No other files need to change.

---

### `pipeline/rules/advance_fee.py`

Implement the following six rules, each as a class inheriting `BaseRule`:

| Class | rule_id | bucket | weight | Trigger condition |
|---|---|---|---|---|
| `CryptoCompensationRule` | `crypto_compensation` | `compensation` | 0.35 | `compensation_type` is not None and contains "usdt", "crypto", "bitcoin", "ethereum", or "token" (case-insensitive) |
| `UnknownContactRule` | `unknown_contact_initiated` | `contact` | 0.20 | `contact_details` matches a raw phone number pattern (digits, spaces, +) with no alphabetic name component |
| `PersonalMessagingPlatformRule` | `personal_messaging_platform` | `contact` | 0.15 | `platform` is not None and matches "whatsapp", "telegram", or "signal" (case-insensitive) |
| `ThirdPartyReferralRule` | `third_party_referral` | `recruitment` | 0.20 | `third_party_recruiter_mentioned` is True OR `referral_code_present` is True |
| `PlatformMigrationRule` | `platform_migration_requested` | `recruitment` | 0.20 | `platform_migration_requested` is True |
| `VagueJobDescriptionRule` | `vague_job_description` | `recruitment` | 0.15 | `job_description` is not None AND contains any of: "no skills", "just use phone", "mobile phone", "easy work", "anyone can", "no experience" (case-insensitive) |

---

### `pipeline/rules/__init__.py`

This is the only file that needs to change when adding a new rule.

```python
from pipeline.rules.advance_fee import (
    CryptoCompensationRule,
    UnknownContactRule,
    PersonalMessagingPlatformRule,
    ThirdPartyReferralRule,
    PlatformMigrationRule,
    VagueJobDescriptionRule,
)
from pipeline.rules.base import BaseRule

RULES: list[BaseRule] = [
    CryptoCompensationRule(),
    UnknownContactRule(),
    PersonalMessagingPlatformRule(),
    ThirdPartyReferralRule(),
    PlatformMigrationRule(),
    VagueJobDescriptionRule(),
]
```

---

### `pipeline/score.py`

Responsibilities: run all rules, aggregate into a composite score, assign label
and summary.

```
BUCKET_CAPS: dict[str, float] = {
    "compensation": 0.40,
    "contact":      0.30,
    "recruitment":  0.40,
}
# Max possible score = sum of caps = 1.10; normalise by dividing by this sum.

run_rules(fields: ExtractedFields) -> list[RuleResult]
    - Call rule.evaluate(fields) for each rule in RULES
    - Return all RuleResults (triggered and not triggered)

aggregate_score(results: list[RuleResult]) -> float
    - Group triggered rules by bucket
    - Sum weights within each bucket, cap at BUCKET_CAPS[bucket]
    - Sum capped bucket totals, divide by sum(BUCKET_CAPS.values()) to normalise to 0-1
    - Return float rounded to 2dp

assign_label(score: float) -> Literal["low", "medium", "high"]
    - score < 0.35  -> "low"
    - score < 0.65  -> "medium"
    - score >= 0.65 -> "high"
    - Note: thresholds are set arbitrarily; in production, tune against labelled data

build_summary(results: list[RuleResult], label: str) -> str
    - Collect explanation strings from triggered rules only
    - Return a single human-readable sentence for an analyst
    - Example: "High risk: cryptocurrency compensation and third-party referral
      indicate an advance fee / job scam pattern."
    - If no rules triggered: return "No significant risk signals detected."

score(fields: ExtractedFields) -> tuple[list[RuleResult], float, str, str]
    - Orchestrates run_rules -> aggregate_score -> assign_label -> build_summary
    - Returns (rule_results, risk_score, label, summary)
    - On any exception: return ([], 0.0, "low",
      "Scoring failed — manual review required.")
```

---

### `app.py`

Streamlit UI. Keep this thin — all logic lives in the pipeline modules.

**Layout:**
- Title and one-line description of the tool
- File uploader accepting pdf, png, jpg, jpeg
- On upload: show `st.spinner` immediately. The spinner appears before the API
  call starts so the UI is never frozen without feedback. This is the only
  latency mitigation needed for a synchronous single-user prototype.
- On result: two columns
  - Left: extracted fields as a formatted JSON block (`st.json`)
  - Right: risk score (large text), risk label as a coloured badge
    (green=low, amber=medium, red=high), human-readable summary,
    then a table of all scoring rules showing rule_id, triggered, weight, explanation
- If `category_confidence < CONFIDENCE_THRESHOLD`: show `st.warning` banner
  above results: "Low confidence classification — results flagged for human review."
  Still display all results.
- On `IngestionError`: show `st.error` with the message. No traceback.
- On any other unhandled exception: show `st.error("Unexpected error — please
  try again or contact support.")`. Log the traceback server-side.

**Processing flow:**
```
file -> ingest.validate_file()       # raises IngestionError on bad input
     -> ingest.prepare_image()       # returns base64 string
     -> extract.extract()            # returns ExtractionResult (never raises)
     -> score.score()                # returns (rules, score, label, summary)
     -> assemble PipelineOutput      # construct final schema
     -> display results
```

---

## Tests

### `tests/test_rules.py`

One trigger test and one no-trigger test per rule. Construct minimal `ExtractedFields`
objects — only populate the fields the rule under test actually reads.

```python
def test_crypto_compensation_triggers():
    fields = ExtractedFields(compensation_type="USDT")
    assert CryptoCompensationRule().evaluate(fields).triggered is True

def test_crypto_compensation_does_not_trigger():
    fields = ExtractedFields(compensation_type="GBP")
    assert CryptoCompensationRule().evaluate(fields).triggered is False
```

### `tests/test_ingest.py`

```
test_rejects_unsupported_filetype     — pass a .docx file, assert IngestionError raised
test_rejects_oversized_file           — pass a file exceeding MAX_FILE_SIZE_MB, assert IngestionError raised
test_rejects_corrupt_image            — pass a PNG with corrupted bytes, assert IngestionError raised
test_rejects_corrupt_pdf              — pass a PDF with corrupted bytes, assert IngestionError raised
test_valid_png_returns_base64         — pass a valid PNG, assert return is a non-empty string
test_valid_pdf_returns_base64         — pass a valid single-page PDF, assert return is a non-empty string
```

### `tests/test_score.py`

```
test_bucket_cap_prevents_double_counting
    — construct two triggered RuleResults in the same bucket whose weights sum > cap
    — assert aggregate_score <= cap / sum(BUCKET_CAPS.values())

test_untriggered_rules_do_not_contribute
    — construct a list with all triggered=False
    — assert aggregate_score == 0.0

test_label_thresholds
    — assert assign_label(0.20) == "low"
    — assert assign_label(0.50) == "medium"
    — assert assign_label(0.80) == "high"

test_no_triggered_rules_summary
    — assert build_summary(all_untriggered, "low") == "No significant risk signals detected."
```

### `tests/test_extract.py`

Mock `call_llm` to return controlled dicts. Test `parse_extraction` in isolation.
Do not make real API calls in unit tests.

```
test_valid_response_parses_correctly
    — mock returns a well-formed dict matching ExtractionResult schema
    — assert processing_metadata.extraction_warnings is empty

test_missing_fields_filled_with_null
    — mock returns a dict with several ExtractedFields fields omitted
    — assert those fields are None in result
    — assert field names appear in processing_metadata.extraction_warnings

test_extra_fields_ignored
    — mock returns a dict with unexpected extra keys
    — assert no ValidationError raised (ConfigDict extra='ignore')

test_complete_parse_failure_returns_safe_result
    — mock call_llm to raise ExtractionParseError
    — assert result.category == "other"
    — assert result.category_confidence == 0.0
    — assert processing_metadata.extraction_warnings contains a failure description
```

---

## Implementation order

Build bottom-up to allow incremental testing at each step:

1. `schemas.py` — all Pydantic models, no dependencies
2. `rules/base.py` — abstract base class
3. `rules/advance_fee.py` — concrete rules
4. `tests/test_rules.py` — run `pytest tests/test_rules.py` and confirm all pass before continuing
5. `ingest.py` — file validation and image prep
6. `tests/test_ingest.py` — confirm validation logic before wiring to UI
7. `score.py` — aggregation logic
8. `tests/test_score.py` — confirm aggregation and capping behaviour
9. `extract.py` — LLM call and parsing
10. `tests/test_extract.py` — confirm parsing with mocked responses
11. `rules/__init__.py` — assemble registry
12. `app.py` — wire everything together in Streamlit

---

## Environment variables

```bash
OPENROUTER_API_KEY=           # required

# Tuneable parameters — kept in env rather than hardcoded to signal they are
# calibration targets, not fixed values. In production both would be tuned
# against labelled data.
MAX_FILE_SIZE_MB=10           # deployment-dependent; may be lower behind a load balancer
CONFIDENCE_THRESHOLD=0.6      # below this, results are flagged for human review
```

---

## Requirements

```
streamlit
openai          # used as OpenRouter client (OpenAI-compatible API)
pydantic>=2.0
pymupdf
Pillow
python-dotenv
pytest
```
