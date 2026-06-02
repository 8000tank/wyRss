"""Unit tests for configuration module."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.config import FetchBucket, Settings, _parse_buckets


class TestSettings:
    """Tests for Settings configuration."""

    def test_from_env_with_valid_values(self, tmp_path: Path, monkeypatch) -> None:
        """Test Settings loads correctly from environment variables."""
        # Set required environment variables
        monkeypatch.setenv("READWISE_TOKEN", "test-token")
        monkeypatch.setenv("READWISE_BASE_URL", "https://readwise.io/api/v3")
        monkeypatch.setenv("RSS_LLM_API_KEY", "test-llm-key")
        monkeypatch.setenv("RSS_LLM_MODEL", "test-model")
        monkeypatch.setenv("RSS_LLM_BASE_URL", "https://api.example.com/v1")
        monkeypatch.setenv("DIGEST_OUTPUT_DIR", str(tmp_path / "output"))
        monkeypatch.setenv("DIGEST_PRE_SCORE_LIMIT", "12")
        monkeypatch.setenv("DIGEST_TIMEZONE", "Asia/Shanghai")
        monkeypatch.setenv("DIGEST_MAX_PUBLISHED_AGE_DAYS", "3")
        monkeypatch.setenv("LLM_CONCURRENCY", "3")
        monkeypatch.setenv("LLM_MAX_TOKENS", "8192")
        monkeypatch.setenv("LLM_REASONING_SPLIT", "true")

        settings = Settings.from_env()

        assert settings.readwise_token == "test-token"
        assert settings.readwise_base_url == "https://readwise.io/api/v3"
        assert settings.llm_api_key == "test-llm-key"
        assert settings.llm_model == "test-model"
        assert settings.llm_base_url == "https://api.example.com/v1"
        assert settings.digest_output_dir == tmp_path / "output"
        assert settings.digest_pre_score_limit == 12
        assert settings.digest_timezone == "Asia/Shanghai"
        assert settings.digest_max_published_age_days == 3
        assert settings.llm_concurrency == 3
        assert settings.llm_max_tokens == 8192
        assert settings.llm_reasoning_split is True
        assert settings.llm_extra_body() == {"reasoning_split": True}

    def test_from_env_with_defaults(self, tmp_path: Path, monkeypatch) -> None:
        """Test Settings uses correct default values."""
        monkeypatch.setattr("src.config.load_dotenv", lambda: None)
        monkeypatch.setenv("READWISE_TOKEN", "test-token")
        monkeypatch.setenv("RSS_LLM_API_KEY", "test-llm-key")
        monkeypatch.setenv("RSS_LLM_MODEL", "test-model")
        monkeypatch.setenv("DIGEST_OUTPUT_DIR", str(tmp_path / "output"))

        # Remove optional values so Settings falls back to its built-in defaults.
        for key in [
            "READWISE_LOCATION",
            "READWISE_CATEGORY",
            "DIGEST_HOURS",
            "DIGEST_CANDIDATE_LIMIT",
            "DIGEST_PRE_SCORE_LIMIT",
            "DIGEST_TOP_N",
            "DIGEST_TIMEZONE",
            "DIGEST_MAX_PUBLISHED_AGE_DAYS",
            "RSS_LLM_BASE_URL",
            "LLM_BASE_URL",
            "LLM_CONCURRENCY",
            "LLM_MAX_TOKENS",
            "LLM_REASONING_SPLIT",
        ]:
            monkeypatch.delenv(key, raising=False)

        settings = Settings.from_env()

        assert settings.readwise_location == "feed"
        assert settings.readwise_category == "rss"
        assert settings.digest_hours == 24
        assert settings.digest_pre_score_limit == 20
        assert settings.digest_top_n == 10
        assert settings.digest_candidate_limit == 30
        assert settings.digest_timezone == "Asia/Shanghai"
        assert settings.digest_max_published_age_days == 7
        assert settings.llm_concurrency == 1
        assert settings.llm_temperature == 0.2
        assert settings.llm_max_tokens == 4096
        assert settings.llm_max_input_chars == 6000
        assert settings.llm_reasoning_split is False

    def test_from_env_missing_required_raises_error(self, monkeypatch) -> None:
        """Test Settings raises error when required variables are missing."""
        # Mock to return empty strings for required vars (simulating missing env vars)
        import os
        original_getenv = os.getenv
        def mock_getenv(name, default=None):
            if name in [
                "READWISE_TOKEN",
                "RSS_LLM_API_KEY",
                "RSS_LLM_MODEL",
                "LLM_API_KEY",
                "LLM_MODEL",
            ]:
                return ""  # Empty string, not None
            return original_getenv(name, default)
        monkeypatch.setattr(os, "getenv", mock_getenv)

        with pytest.raises(ValueError) as exc_info:
            Settings.from_env()

        assert "Missing required environment variables" in str(exc_info.value)
        assert "READWISE_TOKEN" in str(exc_info.value)
        assert "RSS_LLM_API_KEY" in str(exc_info.value)
        assert "RSS_LLM_MODEL" in str(exc_info.value)

    def test_from_env_partial_missing_raises_error(self, monkeypatch) -> None:
        """Test Settings raises error when some required variables are missing."""
        import os
        original_getenv = os.getenv
        def mock_getenv(name, default=None):
            if name == "READWISE_TOKEN":
                return "test-token"
            if name in [
                "RSS_LLM_API_KEY",
                "RSS_LLM_MODEL",
                "LLM_API_KEY",
                "LLM_MODEL",
            ]:
                return ""  # Empty, simulating missing
            return original_getenv(name, default)
        monkeypatch.setattr(os, "getenv", mock_getenv)

        with pytest.raises(ValueError) as exc_info:
            Settings.from_env()

        error_msg = str(exc_info.value)
        assert "RSS_LLM_API_KEY" in error_msg
        assert "RSS_LLM_MODEL" in error_msg

    def test_settings_loads_max_per_site_and_author_defaults(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """When the new diversity knobs are unset, defaults are 2/2."""
        monkeypatch.setattr("src.config.load_dotenv", lambda: None)
        monkeypatch.setenv("READWISE_TOKEN", "test-token")
        monkeypatch.setenv("RSS_LLM_API_KEY", "test-llm-key")
        monkeypatch.setenv("RSS_LLM_MODEL", "test-model")
        monkeypatch.setenv("DIGEST_OUTPUT_DIR", str(tmp_path / "output"))
        for key in [
            "DIGEST_MAX_PER_SITE",
            "DIGEST_MAX_PER_AUTHOR",
            "DIGEST_TOPIC_BUCKETS",
            "READWISE_FETCH_BUCKETS",
        ]:
            monkeypatch.delenv(key, raising=False)

        settings = Settings.from_env()

        assert settings.digest_max_per_site == 2
        assert settings.digest_max_per_author == 2
        assert "ai" in settings.digest_topic_buckets
        assert "other" in settings.digest_topic_buckets
        assert settings.readwise_fetch_buckets == []

    def test_effective_buckets_falls_back_to_legacy_category(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Without READWISE_FETCH_BUCKETS, effective_buckets uses legacy single bucket."""
        monkeypatch.setattr("src.config.load_dotenv", lambda: None)
        monkeypatch.setenv("READWISE_TOKEN", "t")
        monkeypatch.setenv("RSS_LLM_API_KEY", "k")
        monkeypatch.setenv("RSS_LLM_MODEL", "m")
        monkeypatch.setenv("DIGEST_OUTPUT_DIR", str(tmp_path / "out"))
        monkeypatch.setenv("READWISE_CATEGORY", "rss")
        monkeypatch.setenv("DIGEST_CANDIDATE_LIMIT", "33")
        monkeypatch.delenv("READWISE_FETCH_BUCKETS", raising=False)

        settings = Settings.from_env()

        assert settings.effective_buckets() == [FetchBucket(category="rss", max_items=33)]

    def test_effective_buckets_uses_parsed_specs_when_present(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setattr("src.config.load_dotenv", lambda: None)
        monkeypatch.setenv("READWISE_TOKEN", "t")
        monkeypatch.setenv("RSS_LLM_API_KEY", "k")
        monkeypatch.setenv("RSS_LLM_MODEL", "m")
        monkeypatch.setenv("DIGEST_OUTPUT_DIR", str(tmp_path / "out"))
        monkeypatch.setenv("READWISE_FETCH_BUCKETS", "rss@feed:60,email@new:20")

        settings = Settings.from_env()

        assert settings.effective_buckets() == [
            FetchBucket(category="rss", location="feed", max_items=60),
            FetchBucket(category="email", location="new", max_items=20),
        ]

    def test_minimax_m2_defaults_to_reasoning_split(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setattr("src.config.load_dotenv", lambda: None)
        monkeypatch.setenv("READWISE_TOKEN", "t")
        monkeypatch.setenv("RSS_LLM_API_KEY", "k")
        monkeypatch.setenv("RSS_LLM_BASE_URL", "https://api.minimaxi.com/v1")
        monkeypatch.setenv("RSS_LLM_MODEL", "MiniMax-M2.7")
        monkeypatch.setenv("DIGEST_OUTPUT_DIR", str(tmp_path / "out"))
        monkeypatch.delenv("LLM_REASONING_SPLIT", raising=False)

        settings = Settings.from_env()

        assert settings.llm_reasoning_split is True
        assert settings.llm_extra_body() == {"reasoning_split": True}

    def test_minimax_m3_defaults_to_reasoning_split(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setattr("src.config.load_dotenv", lambda: None)
        monkeypatch.setenv("READWISE_TOKEN", "t")
        monkeypatch.setenv("RSS_LLM_API_KEY", "k")
        monkeypatch.setenv("RSS_LLM_BASE_URL", "https://api.minimaxi.com/v1")
        monkeypatch.setenv("RSS_LLM_MODEL", "MiniMax-M3")
        monkeypatch.setenv("DIGEST_OUTPUT_DIR", str(tmp_path / "out"))
        monkeypatch.delenv("LLM_REASONING_SPLIT", raising=False)

        settings = Settings.from_env()

        assert settings.llm_reasoning_split is True
        assert settings.llm_extra_body() == {"reasoning_split": True}

    def test_minimax_global_api_defaults_to_reasoning_split(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setattr("src.config.load_dotenv", lambda: None)
        monkeypatch.setenv("READWISE_TOKEN", "t")
        monkeypatch.setenv("RSS_LLM_API_KEY", "k")
        monkeypatch.setenv("RSS_LLM_BASE_URL", "https://api.minimax.io/v1")
        monkeypatch.setenv("RSS_LLM_MODEL", "MiniMax-M3")
        monkeypatch.setenv("DIGEST_OUTPUT_DIR", str(tmp_path / "out"))
        monkeypatch.delenv("LLM_REASONING_SPLIT", raising=False)

        settings = Settings.from_env()

        assert settings.llm_reasoning_split is True
        assert settings.llm_extra_body() == {"reasoning_split": True}

    def test_reasoning_split_can_be_explicitly_disabled(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setattr("src.config.load_dotenv", lambda: None)
        monkeypatch.setenv("READWISE_TOKEN", "t")
        monkeypatch.setenv("RSS_LLM_API_KEY", "k")
        monkeypatch.setenv("RSS_LLM_BASE_URL", "https://api.minimaxi.com/v1")
        monkeypatch.setenv("RSS_LLM_MODEL", "MiniMax-M2.7")
        monkeypatch.setenv("LLM_REASONING_SPLIT", "false")
        monkeypatch.setenv("DIGEST_OUTPUT_DIR", str(tmp_path / "out"))

        settings = Settings.from_env()

        assert settings.llm_reasoning_split is False
        assert settings.llm_extra_body() == {}


class TestParseBuckets:
    """Tests for the _parse_buckets helper."""

    def test_parse_buckets_valid(self) -> None:
        assert _parse_buckets("rss:60,email:20") == [
            FetchBucket(category="rss", max_items=60),
            FetchBucket(category="email", max_items=20),
        ]

    def test_parse_buckets_with_location_overrides(self) -> None:
        assert _parse_buckets("rss@feed:60,email@new:20") == [
            FetchBucket(category="rss", location="feed", max_items=60),
            FetchBucket(category="email", location="new", max_items=20),
        ]

    def test_parse_buckets_strips_whitespace(self) -> None:
        assert _parse_buckets("  rss @ feed : 60 , email @ new :20  ") == [
            FetchBucket(category="rss", location="feed", max_items=60),
            FetchBucket(category="email", location="new", max_items=20),
        ]

    def test_parse_buckets_empty_returns_empty_list(self) -> None:
        assert _parse_buckets("") == []
        assert _parse_buckets(None) == []
        assert _parse_buckets("   ") == []

    def test_parse_buckets_malformed_entries_are_skipped(self) -> None:
        # Mix valid + malformed entries; only valid survives.
        result = _parse_buckets("rss:60,bogus,email:notnum,html:0,article:-1,email:20")
        assert result == [
            FetchBucket(category="rss", max_items=60),
            FetchBucket(category="email", max_items=20),
        ]

    def test_parse_buckets_empty_category_means_all_categories(self) -> None:
        # Empty category before colon -> None (means "no category filter").
        assert _parse_buckets(":50") == [FetchBucket(category=None, max_items=50)]

    def test_parse_buckets_duplicate_category_last_wins(self) -> None:
        # First occurrence preserves order; later value overwrites the count.
        assert _parse_buckets("rss:10,email:5,rss:99") == [
            FetchBucket(category="rss", max_items=99),
            FetchBucket(category="email", max_items=5),
        ]
