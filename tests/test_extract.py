"""Unit tests for extraction parsing with mocked LLM responses."""

from unittest.mock import Mock, patch

import pytest

from pipeline.extract import (
    ExtractionParseError,
    LLMCallError,
    extract,
    parse_extraction,
)
from pipeline.schemas import ExtractedFields


def test_valid_response_parses_correctly():
    """Test that a well-formed response parses without warnings."""
    raw = {
        "category": "chat_screenshot",
        "category_confidence": 0.95,
        "extracted_fields": {
            "entity_name": "ACME Corp",
            "amount": 100.50,
            "currency": "GBP",
            "date": "2024-01-15",
            "counterparty": "John Doe",
            "platform": "WhatsApp",
            "contact_details": "+44 123 456 7890",
            "red_flags": ["unknown_contact_initiated"],
        },
    }

    result = parse_extraction(raw, "test-model", 1000)

    assert result.category == "chat_screenshot"
    assert result.category_confidence == 0.95
    assert result.extracted_fields.entity_name == "ACME Corp"
    assert result.extracted_fields.amount == 100.50
    assert result.extracted_fields.currency == "GBP"
    assert len(result.processing_metadata.extraction_warnings) == 0


def test_missing_fields_filled_with_null():
    """Test that missing fields are detected and filled with None."""
    # Dict with some fields missing entirely (not present as keys)
    raw = {
        "category": "invoice",
        "category_confidence": 0.8,
        "extracted_fields": {
            "entity_name": "ACME Corp",
            "date": "2024-01-15",
            # amount and currency are completely absent
            "counterparty": None,  # This one is explicitly null
            "platform": "Email",
            # contact_details is absent
            "red_flags": [],
        },
    }

    result = parse_extraction(raw, "test-model", 1000)

    # Fields should be None
    assert result.extracted_fields.amount is None
    assert result.extracted_fields.currency is None
    assert result.extracted_fields.contact_details is None

    # Warnings should indicate these were not returned
    warnings = result.processing_metadata.extraction_warnings
    assert any("amount: not returned by model" in w for w in warnings)
    assert any("currency: not returned by model" in w for w in warnings)
    assert any("contact_details: not returned by model" in w for w in warnings)


def test_extra_fields_ignored():
    """Test that unexpected extra fields don't cause validation errors."""
    raw = {
        "category": "other",
        "category_confidence": 0.5,
        "extracted_fields": {
            "entity_name": "Test",
            "amount": None,
            "currency": None,
            "date": None,
            "counterparty": None,
            "platform": None,
            "contact_details": None,
            "red_flags": [],
            "unexpected_field": "this should be ignored",
            "another_extra": 123,
        },
        "extra_top_level": "also ignored",
    }

    # Should not raise ValidationError due to ConfigDict(extra='ignore')
    result = parse_extraction(raw, "test-model", 1000)

    assert result.category == "other"
    # No validation errors for extra fields
    validation_warnings = [
        w
        for w in result.processing_metadata.extraction_warnings
        if "unexpected" in w.lower() or "extra" in w.lower()
    ]
    assert len(validation_warnings) == 0


def test_complete_parse_failure_returns_safe_result():
    """Test handling of complete parse failure."""
    # Mock call_llm to raise ExtractionParseError
    with patch("pipeline.extract.call_llm") as mock_call:
        mock_call.side_effect = ExtractionParseError("Invalid response format")

        result = extract("fake_base64_image")

        assert result.category == "other"
        assert result.category_confidence == 0.0
        assert result.extracted_fields.entity_name is None
        assert result.extracted_fields.amount is None
        assert any(
            "parse failed" in w.lower()
            for w in result.processing_metadata.extraction_warnings
        )


def test_llm_call_failure_returns_safe_result():
    """Test handling of LLM call failure."""
    # Mock call_llm to raise LLMCallError
    with patch("pipeline.extract.call_llm") as mock_call:
        mock_call.side_effect = LLMCallError("API timeout")

        result = extract("fake_base64_image")

        assert result.category == "other"
        assert result.category_confidence == 0.0
        assert any(
            "call failed" in w.lower()
            for w in result.processing_metadata.extraction_warnings
        )


def test_wrong_type_fields_handled():
    """Test that wrong-type fields are handled gracefully."""
    raw = {
        "category": "invoice",
        "category_confidence": "not a float",  # Wrong type
        "extracted_fields": {
            "entity_name": "Test",
            "amount": "one hundred",  # Wrong type, should be float
            "currency": "USD",
            "date": None,
            "counterparty": None,
            "platform": None,
            "contact_details": None,
            "red_flags": [],
        },
    }

    result = parse_extraction(raw, "test-model", 1000)

    # Should still return a result, possibly with warnings
    assert result is not None
    # Amount should be None due to wrong type
    assert result.extracted_fields.amount is None
