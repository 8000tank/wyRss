"""Unit tests for configuration module."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.config import Settings


class TestSettings:
    """Tests for Settings configuration."""

    def test_from_env_with_valid_values(self, tmp_path: Path, monkeypatch) -> None:
        """Test Settings loads correctly from environment variables."""
        # Set required environment variables
        monkeypatch.setenv("READWISE_TOKEN", "test-token")
        monkeypatch.setenv("READWISE_BASE_URL", "https://readwise.io/api/v3")
        monkeypatch.setenv("LLM_API_KEY", "test-llm-key")
        monkeypatch.setenv("LLM_MODEL", "test-model")
        monkeypatch.setenv("LLM_BASE_URL", "https://api.example.com/v1")
        monkeypatch.setenv("DIGEST_OUTPUT_DIR", str(tmp_path / "output"))

        settings = Settings.from_env()

        assert settings.readwise_token == "test-token"
        assert settings.readwise_base_url == "https://readwise.io/api/v3"
        assert settings.llm_api_key == "test-llm-key"
        assert settings.llm_model == "test-model"
        assert settings.llm_base_url == "https://api.example.com/v1"
        assert settings.digest_output_dir == tmp_path / "output"

    def test_from_env_with_defaults(self, tmp_path: Path, monkeypatch) -> None:
        """Test Settings uses correct default values."""
        monkeypatch.setenv("READWISE_TOKEN", "test-token")
        monkeypatch.setenv("LLM_API_KEY", "test-llm-key")
        monkeypatch.setenv("LLM_MODEL", "test-model")
        monkeypatch.setenv("DIGEST_OUTPUT_DIR", str(tmp_path / "output"))

        # Unset optional variables to test defaults
        for key in ["READWISE_LOCATION", "READWISE_CATEGORY", "DIGEST_HOURS", "DIGEST_TOP_N"]:
            monkeypatch.delenv(key, raising=False)

        settings = Settings.from_env()

        assert settings.readwise_location == "feed"
        assert settings.readwise_category == "rss"
        assert settings.digest_hours == 24
        assert settings.digest_top_n == 10
        assert settings.digest_candidate_limit == 30
        assert settings.llm_temperature == 0.2
        assert settings.llm_max_input_chars == 6000

    def test_from_env_missing_required_raises_error(self, monkeypatch) -> None:
        """Test Settings raises error when required variables are missing."""
        # Mock to return empty strings for required vars (simulating missing env vars)
        import os
        original_getenv = os.getenv
        def mock_getenv(name, default=None):
            if name in ["READWISE_TOKEN", "LLM_API_KEY", "LLM_MODEL"]:
                return ""  # Empty string, not None
            return original_getenv(name, default)
        monkeypatch.setattr(os, "getenv", mock_getenv)

        with pytest.raises(ValueError) as exc_info:
            Settings.from_env()

        assert "Missing required environment variables" in str(exc_info.value)
        assert "READWISE_TOKEN" in str(exc_info.value)
        assert "LLM_API_KEY" in str(exc_info.value)
        assert "LLM_MODEL" in str(exc_info.value)

    def test_from_env_partial_missing_raises_error(self, monkeypatch) -> None:
        """Test Settings raises error when some required variables are missing."""
        import os
        original_getenv = os.getenv
        def mock_getenv(name, default=None):
            if name == "READWISE_TOKEN":
                return "test-token"
            if name in ["LLM_API_KEY", "LLM_MODEL"]:
                return ""  # Empty, simulating missing
            return original_getenv(name, default)
        monkeypatch.setattr(os, "getenv", mock_getenv)

        with pytest.raises(ValueError) as exc_info:
            Settings.from_env()

        error_msg = str(exc_info.value)
        assert "LLM_API_KEY" in error_msg
        assert "LLM_MODEL" in error_msg
