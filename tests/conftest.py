"""Pytest configuration and shared fixtures."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.models import Article


@pytest.fixture
def sample_article() -> Article:
    """Return a sample article for testing."""
    return Article(
        id="test-id-001",
        title="Test Article Title",
        url="https://read.readwise.io/read/test-id-001",
        source_url="https://example.com/article-1",
        author="Test Author",
        source="Test Source",
        category="article",
        location="new",
        site_name="Test Site",
        word_count=1500,
        reading_time="6 mins",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        published_date=None,
        summary="This is a test summary from Readwise.",
        image_url="https://example.com/image.jpg",
        notes="",
        reading_progress=0.5,
        tags=["test", "example"],
        html_content="<p>This is the HTML content of the article.</p>",
        text_content="This is the text content of the article.",
        parent_id=None,
    )


@pytest.fixture
def sample_articles_list() -> list[Article]:
    """Return a list of sample articles for testing."""
    base_time = datetime.now(timezone.utc)
    return [
        Article(
            id=f"test-id-{i:03d}",
            title=f"Test Article {i}",
            url=f"https://read.readwise.io/read/test-id-{i:03d}",
            source_url=f"https://example.com/article-{i}",
            author=f"Author {i}",
            source="Test Source",
            category="article",
            location="new",
            site_name=f"Site {i}",
            word_count=1000 + i * 100,
            reading_time=f"{5 + i} mins",
            created_at=base_time,
            updated_at=base_time,
            published_date=None,
            summary=f"Summary for article {i}",
            image_url=None,
            notes="",
            reading_progress=0.0,
            tags=["tag1", "tag2"] if i % 2 == 0 else ["tag3"],
            html_content=f"<p>Content {i}</p>",
            text_content=f"Content {i}",
            parent_id=None,
        )
        for i in range(1, 6)
    ]


@pytest.fixture
def mock_env_vars(tmp_path: Path) -> dict[str, str]:
    """Return mock environment variables for testing."""
    return {
        "READWISE_TOKEN": "test-readwise-token",
        "READWISE_BASE_URL": "https://readwise.io/api/v3",
        "READWISE_LOCATION": "feed",
        "READWISE_CATEGORY": "rss",
        "READWISE_WITH_HTML_CONTENT": "true",
        "REQUEST_TIMEOUT_SECONDS": "30",
        "DIGEST_HOURS": "24",
        "DIGEST_CANDIDATE_LIMIT": "30",
        "DIGEST_TOP_N": "10",
        "DIGEST_OUTPUT_DIR": str(tmp_path / "output"),
        "DIGEST_LANGUAGE": "中文",
        "DIGEST_SCORING_FOCUS": "测试用排序目标",
        "LLM_API_KEY": "test-llm-api-key",
        "LLM_BASE_URL": "https://api.example.com/v1",
        "LLM_MODEL": "test-model",
        "LLM_TIMEOUT_SECONDS": "60",
        "LLM_TEMPERATURE": "0.2",
        "LLM_MAX_INPUT_CHARS": "6000",
    }
