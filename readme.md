# Document categorization and risk extraction

This is a document analysis pipeline for AI-assisted fraud operations on UK Faster Payments, intended to help fraud analysts decide whether to stop or release a suspicious payment based on documentary evidence provided by the payer. It ingests uploaded evidence (PDF/image), uses an LLM to extract structured signals, and applies deterministic rules to produce an explainable low/medium/high risk assessment. 

Topics covered:
- LLM prompt / schema design, structured output enforcement
- Deterministic rules engine on top of LLM outputs
- Human-in-the-loop review
- Pydantic for schema validation and evals against a golden document set
- Multi-agent orchestration with LangGraph
- Observability, including with LangSmith
- Robust failure handling

# Architecture

```
frontend/   React + TypeScript SPA (Vite, Tailwind)
api/        FastAPI backend — wraps the pipeline for HTTP
pipeline/   Core logic: ingest, classify, extract, score 
```

The frontend is served by nginx (port 3000). nginx proxies `/api/*` to the FastAPI service (port 8000). 

# Running the app

## Set up the env file

Copy `.env.example` to `.env` and fill in your values. The app runs fully offline by default (no API key needed) using local fixture data.

```sh
cp .env.example .env
```

## With Docker Compose (recommended)

```sh
docker compose up --build
```

- Frontend: [http://localhost:3000](http://localhost:3000)
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

> Uploaded files are processed in-memory and never written to disk. The only persistent output is the run log at `logs/pipeline_runs.jsonl` (mounted volume).

## Local development (no Docker)

**API** (terminal 1):
```sh
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

**Frontend** (terminal 2):
```sh
cd frontend
npm install
npm run dev        # Vite dev server at http://localhost:5173
```

The Vite dev server proxies `/api` to `http://localhost:8000` automatically.

## Tests

**Python** (pipeline unit tests + API endpoint tests, fully offline):
```sh
python3 -m pytest tests/
```

**TypeScript** (component + api client tests):
```sh
cd frontend
npm test
```

## Using the UI

Upload a file and choose single-model or multi-agent mode: 
![](./examples/run_through/upload.png)

Review the extracted fields for correctness before you submit for risk flagging:
![](./examples/run_through/review.png)

Finally, review the model risk assessment (you can also review the processing metadata, output JSON, and the traced run log):
![](./examples/run_through/output.png)

## Evals

A small eval suite lives in `tests/evals/` using [Pydantic Evals](https://ai.pydantic.dev/evals/).
Evals run the full pipeline against a golden document and assert on the output.
Unlike unit tests, evals make real calls to the OpenRouter API because some tests involve LLM-as-a-judge. 
Therefore, you need to have a valid `OPENROUTER_API_KEY` in `.env`. Evals are run using the model name specified by `LLM_MODEL_NAME` in `pipeline/constants.py`. 

To run (requires `OPENROUTER_API_KEY` in `.env`):

```sh
$ ALLOW_NETWORK_CALLS=true python -m pytest tests/evals/ -m integration
```

Note: eval tests are marked `@pytest.mark.integration` and are excluded from the default `pytest tests/` run so they don't fire in offline / CI mode.

### Evaluator summary

| Eval | Field | Type | Rationale |
|---|---|---|---|
| json_valid | (structural) | Deterministic | Malformed JSON is unambiguous pass/fail |
| category_correct | category | Deterministic | Bounded Literal set — exact equality appropriate |
| risk_label_correct | risk_label | Deterministic | Bounded Literal set — tests full pipeline end-to-end |
| amount_correct | extracted_fields.amount | Deterministic | Unambiguous numeric value |
| currency_correct | extracted_fields.currency | Deterministic | Unambiguous string — case-insensitive equality |
| contact_details_correct | extracted_fields.contact_details | LLM-as-judge | Phone formatting varies — judge handles format variation |
| counterparty_correct | extracted_fields.counterparty | LLM-as-judge | Freeform name field — exact match too strict |
| red_flags_no_judgements | extracted_fields.red_flags | LLM-as-judge | Detecting evaluative language requires semantic understanding |

# Configuration

## Adding a new rule

1. Create a new rule class in [`pipeline/rules/`](pipeline/rules/) that inherits from `BaseRule`
2. Implement the `evaluate()` method to return a `RuleResult`
3. Add the rule instance to the `RULES` list in [`pipeline/rules/__init__.py`](pipeline/rules/__init__.py)

See [`pipeline/rules/advance_fee.py`](pipeline/rules/advance_fee.py) for examples.

## Changing the model

Edit `LLM_MODEL_NAME` in [`pipeline/constants.py`](pipeline/constants.py). Any OpenRouter-supported model can be used.

## Changing risk thresholds

Edit `RISK_THRESHOLD_LOW_MEDIUM` and `RISK_THRESHOLD_MEDIUM_HIGH` in [`pipeline/constants.py`](pipeline/constants.py). These control the low/medium/high risk label boundaries.

## Adding a new golden document to the evals

1. Add the file to `tests/evals/golden_set/`
2. Create a corresponding `_expected.json` with known correct field values
3. Add a new `Case` to the `dataset` in `test_evals.py`
4. No changes to `evals.py` are needed unless you want to add new evaluator types
