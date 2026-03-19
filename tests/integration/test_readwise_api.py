"""Integration tests for Readwise Reader API.

These tests make real API calls using the configured environment variables.
Run with: pytest tests/integration/test_readwise_api.py -v
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

from src.clients.readwise_client import ReadwiseClient
from src.config import Settings


@pytest.fixture
def real_readwise_client() -> ReadwiseClient:
    """Create a Readwise client using real environment variables."""
    settings = Settings.from_env()
    return ReadwiseClient(
        token=settings.readwise_token,
        base_url=settings.readwise_base_url,
        timeout_seconds=settings.request_timeout_seconds,
    )


@pytest.mark.integration
class TestReadwiseAPI:
    """Integration tests for Readwise Reader API."""

    def test_verify_token(self, real_readwise_client: ReadwiseClient) -> None:
        """Test that the configured Readwise token is valid."""
        try:
            real_readwise_client.verify_token()
            print("\n✓ Readwise token verified successfully")
        except Exception as e:
            pytest.fail(f"Token verification failed: {e}")

    def test_list_documents_basic(self, real_readwise_client: ReadwiseClient) -> None:
        """Test listing documents from Readwise Reader."""
        settings = Settings.from_env()

        articles = real_readwise_client.list_documents(
            location=settings.readwise_location,
            category=settings.readwise_category,
            with_html_content=False,
            limit_per_page=10,
            max_items=5,
        )

        assert isinstance(articles, list)
        print(f"\n✓ Retrieved {len(articles)} documents from Readwise")

        if articles:
            article = articles[0]
            print(f"  - First article: {article.title}")
            print(f"  - URL: {article.canonical_url}")
            print(f"  - Category: {article.category}")
            print(f"  - Location: {article.location}")

    def test_list_documents_with_time_filter(self, real_readwise_client: ReadwiseClient) -> None:
        """Test listing documents with updatedAfter filter."""
        settings = Settings.from_env()
        hours_ago = datetime.now(timezone.utc) - timedelta(hours=settings.digest_hours)

        articles = real_readwise_client.list_documents(
            updated_after=hours_ago,
            location=settings.readwise_location,
            category=settings.readwise_category,
            with_html_content=False,
            limit_per_page=20,
            max_items=settings.digest_candidate_limit,
        )

        assert isinstance(articles, list)
        print(f"\n✓ Retrieved {len(articles)} documents from last {settings.digest_hours} hours")

        if articles:
            for i, article in enumerate(articles[:3], 1):
                print(f"  {i}. {article.title[:50]}... (updated: {article.updated_at})")

    def test_list_documents_with_html_content(self, real_readwise_client: ReadwiseClient) -> None:
        """Test listing documents with HTML content extraction."""
        settings = Settings.from_env()
        hours_ago = datetime.now(timezone.utc) - timedelta(hours=settings.digest_hours)

        articles = real_readwise_client.list_documents(
            updated_after=hours_ago,
            location=settings.readwise_location,
            category=settings.readwise_category,
            with_html_content=True,
            limit_per_page=5,
            max_items=2,
        )

        if articles:
            article = articles[0]
            print(f"\n✓ Retrieved article with HTML content:")
            print(f"  - Title: {article.title}")
            print(f"  - Has HTML: {article.html_content is not None}")
            print(f"  - Has text: {article.text_content is not None}")

            if article.text_content:
                preview = article.text_content[:200]
                print(f"  - Text preview: {preview}...")


@pytest.mark.skipif(
    not os.getenv("READWISE_TOKEN"),
    reason="READWISE_TOKEN not set"
)
def test_configuration_loaded() -> None:
    """Test that Readwise configuration can be loaded."""
    settings = Settings.from_env()
    assert settings.readwise_token
    assert settings.readwise_base_url == "https://readwise.io/api/v3"
    print(f"\n✓ Configuration loaded:")
    print(f"  - Base URL: {settings.readwise_base_url}")
    print(f"  - Location: {settings.readwise_location}")
    print(f"  - Category: {settings.readwise_category}")
