"""Unit tests for data models."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from src.models import Article, ScoredArticle


class TestArticle:
    """Tests for Article dataclass."""

    def test_article_creation(self) -> None:
        """Test creating an Article instance."""
        article = Article(
            id="test-001",
            title="Test Title",
            url="https://example.com/article",
            source_url="https://source.com/original",
            author="John Doe",
            source="Test Source",
            category="article",
            location="new",
            site_name="Test Site",
            word_count=1000,
            reading_time="5 mins",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            published_date=date(2024, 1, 1),
            summary="Test summary",
            image_url="https://example.com/image.jpg",
            notes="Some notes",
            reading_progress=0.5,
            tags=["tag1", "tag2"],
            html_content="<p>HTML content</p>",
            text_content="Text content",
            parent_id=None,
        )

        assert article.id == "test-001"
        assert article.title == "Test Title"
        assert article.canonical_url == "https://source.com/original"

    def test_article_canonical_url_fallback(self) -> None:
        """Test canonical_url falls back to url when source_url is None."""
        article = Article(
            id="test-002",
            title="Test Title",
            url="https://example.com/article",
            source_url=None,
            author=None,
            source=None,
            category=None,
            location=None,
            site_name=None,
            word_count=None,
            reading_time=None,
            created_at=None,
            updated_at=None,
            published_date=None,
            summary=None,
            image_url=None,
            notes=None,
            reading_progress=None,
        )

        assert article.canonical_url == "https://example.com/article"

    def test_article_with_parent_id_is_filtered(self) -> None:
        """Test articles with parent_id are child documents."""
        article = Article(
            id="highlight-001",
            title="Highlight",
            url="https://example.com/highlight",
            source_url=None,
            author=None,
            source=None,
            category="highlight",
            location=None,
            site_name=None,
            word_count=None,
            reading_time=None,
            created_at=None,
            updated_at=None,
            published_date=None,
            summary=None,
            image_url=None,
            notes=None,
            reading_progress=None,
            parent_id="parent-article-001",
        )

        assert article.parent_id is not None
        assert article.category == "highlight"


class TestScoredArticle:
    """Tests for ScoredArticle dataclass."""

    def test_scored_article_creation(self) -> None:
        """Test creating a ScoredArticle instance."""
        article = Article(
            id="test-003",
            title="Scored Article",
            url="https://example.com/scored",
            source_url=None,
            author=None,
            source=None,
            category=None,
            location=None,
            site_name=None,
            word_count=None,
            reading_time=None,
            created_at=None,
            updated_at=None,
            published_date=None,
            summary=None,
            image_url=None,
            notes=None,
            reading_progress=None,
        )

        scored = ScoredArticle(
            article=article,
            overall_score=85,
            relevance_score=90,
            novelty_score=80,
            actionability_score=85,
            summary="Generated summary",
            recommendation="Highly recommended",
            keywords=["AI", "tech", "future"],
            raw_response='{"overall_score": 85}',
        )

        assert scored.article.id == "test-003"
        assert scored.overall_score == 85
        assert scored.keywords == ["AI", "tech", "future"]
