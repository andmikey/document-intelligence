"""Tests for LLM backends: local fixture replay and network guard."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from pipeline.agent.backends import LocalFixtureBackend, get_backend
from pipeline.constants import LOCAL_DEV_MODE

# ---------------------------------------------------------------------------
# LocalFixtureBackend
# ---------------------------------------------------------------------------


class TestLocalFixtureBackend:
    def test_classify_returns_category_and_confidence(self):
        backend = LocalFixtureBackend()
        result = backend.classify("fake_b64_image")
        assert "category" in result
        assert "category_confidence" in result
        assert isinstance(result["category"], str)
        assert 0.0 <= result["category_confidence"] <= 1.0

    def test_classify_default_is_chat_screenshot(self):
        backend = LocalFixtureBackend()
        result = backend.classify("any_image")
        assert result["category"] == "chat_screenshot"

    def test_extract_returns_expected_fields(self):
        backend = LocalFixtureBackend()
        result = backend.extract("any_image", "chat_screenshot")
        assert "red_flags" in result
        assert isinstance(result["red_flags"], list)

    def test_extract_fixture_has_known_platform(self):
        backend = LocalFixtureBackend()
        result = backend.extract("any_image", "chat_screenshot")
        assert result.get("platform") == "Telegram"

    def test_sha256_prefix_lookup_falls_back_to_default(self):
        """Images without an explicit fixture entry return the 'default' entry."""
        backend = LocalFixtureBackend()
        result = backend.classify("completely_unknown_image_bytes")
        assert result["category"] == "chat_screenshot"

    def test_custom_fixture_path(self, tmp_path):
        """Backend accepts custom fixture paths."""
        clf = tmp_path / "clf.json"
        ext = tmp_path / "ext.json"
        clf.write_text(
            json.dumps({"default": {"category": "invoice", "category_confidence": 0.9}})
        )
        ext.write_text(
            json.dumps({"default": {"entity_name": "Acme", "red_flags": []}})
        )
        backend = LocalFixtureBackend(classifier_fixture=clf, extractor_fixture=ext)
        assert backend.classify("x")["category"] == "invoice"
        assert backend.extract("x", "invoice")["entity_name"] == "Acme"

    def test_per_image_override(self, tmp_path):
        """A sha256-prefixed entry overrides the default for a specific image."""
        import hashlib

        image_b64 = "special_image_bytes"
        prefix = hashlib.sha256(image_b64.encode()).hexdigest()[:12]

        clf = tmp_path / "clf.json"
        clf.write_text(
            json.dumps(
                {
                    "default": {"category": "other", "category_confidence": 0.5},
                    prefix: {"category": "invoice", "category_confidence": 0.99},
                }
            )
        )
        ext = tmp_path / "ext.json"
        ext.write_text(json.dumps({"default": {"red_flags": []}}))

        backend = LocalFixtureBackend(classifier_fixture=clf, extractor_fixture=ext)
        assert backend.classify(image_b64)["category"] == "invoice"
        assert backend.classify("other_image")["category"] == "other"


# ---------------------------------------------------------------------------
# get_backend factory
# ---------------------------------------------------------------------------


class TestGetBackend:
    def test_returns_local_fixture_backend_by_default(self):
        """With LOCAL_DEV_MODE=true (default), get_backend() returns LocalFixtureBackend."""
        with patch.dict(
            "os.environ", {"LOCAL_DEV_MODE": "true", "ALLOW_NETWORK_CALLS": "false"}
        ):
            # Re-import to pick up patched env
            import importlib

            import pipeline.constants as c
            import pipeline.agent.backends as b

            importlib.reload(c)
            importlib.reload(b)
            backend = b.get_backend()
            assert isinstance(backend, b.LocalFixtureBackend)

    def test_openrouter_backend_raises_without_network_calls(self):
        """OpenRouterBackend refuses to instantiate when ALLOW_NETWORK_CALLS=false."""
        import pipeline.agent.backends as b

        with patch.object(b, "ALLOW_NETWORK_CALLS", False):
            with pytest.raises(RuntimeError, match="ALLOW_NETWORK_CALLS"):
                b.OpenRouterBackend()

    def test_openrouter_backend_raises_without_api_key(self):
        """OpenRouterBackend raises if API key is missing even when network is allowed."""
        import pipeline.agent.backends as b

        with patch.object(b, "ALLOW_NETWORK_CALLS", True):
            with patch.dict("os.environ", {}, clear=True):
                with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
                    b.OpenRouterBackend()
