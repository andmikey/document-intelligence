# Approach

This document summarizes our approach to implementing the given spec. It should be read in conjunction with the [assumptions document](./assumptions.md). 

## Fraud context
- We assume the platform is being used by an analyst to make a decision on whether to let through a high-risk FPS transaction flagged by an upstream system. This decision is based on the risk score and explanation returned by the platform.
- Since this is a time-bounded exercise, we'll focus on one fraud typology: job scam / advance fee fraud (chat_screenshot.jpg provided). 

## Rules
- Rules are implemented in Python, rather than in e.g. a DSL or using a rules engine. 
- Each rule aims to capture a specific, explainable aspect of a fraud typology.  
- LLM/rule boundary: LLM observes / describes what is in the document, given a set of pre-defined red flags in the prompt. The rules interpret observations into a risk score. 
- Feature ideas:
    - Based on the picture:
        - Unknown contact (number not saved)
        - Platform is Telegram/WhatsApp (high risk)
        - Compensation in USDT/crypto
        - Domain age checks
    - Based on the payment:
        - Recipient account is personal, not business, account
        - Recipient account details don't match nam of contact 
- Explanations:
    - Group into fraud typologies (e.g. 1st party, invoice fraud, purchase scam, impersonation scam, advance fee scam, romance scam, investment scam) to get an overall typology. 
    - Explain which specific fraud rules triggered - human-readable summary of rule.
- Aggregation: 
    - Weighted sum is simplest (each rule has weight, final score is sum of triggered rules, normalized to 0-1). Problem is this double-fires on correlated rules. 
    - Alternative is thematic grouping and cap contribution per category.
    - We'll choose category thresholds arbitrarily - in a real system you would tune these against a historical dataset. 
    - Some rules triggering may be enough to create a high risk score by themselves, but this won't be in scope here.
- Versioning: would keep rule versioning in a feature store (maps rule ID -> rule contents). Out of scope for this project. 
- Logging: list of rules triggering on each event should be logged centrally, to allow analysis / tracking of rule performance. Out of scope for this project. 

## Model
- Ensuring a consistent input: temperature of 0 (or near 0) + maybe top-k sampling.
- Ensuring outputs are correct format: JSON mode / tool-calling.
- Need to also get model confidence on classification.
    - Not sure OpenRouter provides this.
    - Easiest option is asking model to self-score. Uncalibrated + likely to be overconfident.   
    - Possible future directions: 
        - Fine-tune a classifier directly on top of the document embeddings. Could then calibrate this score directly.  
- Errors to consider:
    - Malformed JSON: try to parse, otherwise give up and log.
    - Missing required fields. Fill with null and log warning.
    - Refusal to process (e.g. identifies as harmful content): log warning.
    - API rate limit / timeout: could add a try/catch + expontential backoff. 

## Inputs
- Failure modes to consider:
    - Unsupported filetype (not PDF / JPG / PNG)
    - Corrupt file 
    - File too large (set a reasonable upper limit)
    - File contains sensitive data (will not implement due to time constraint)

## Performance evaluation
- We will run predictions online rather than in batch due to the small scale. In practice you'd probably want to run in small near-real-time batches to reduce inference cost. 
- We will not cache anything. Caching prompts could be an easy way to reduce inference cost. 
- Logging: cost of query, latency of query