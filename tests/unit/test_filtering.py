"""Unit tests for article filtering pipeline."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.models import Article
from src.pipeline.filtering import filter_articles


class TestFiltering:
    """Tests for the filtering module."""

    def test_filter_articles_basic(self, sample_articles_list: list[Article]) -> None:
        """Test basic article filtering with time window."""
        # All articles are from now, should all pass
        result = filter_articles(
            sample_articles_list,
            hours=24,
            max_candidates=10,
        )

        assert len(result) == 5

    def test_filter_articles_with_time_window(self) -> None:
        """Test filtering articles outside time window."""
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(hours=48)

        articles = [
            Article(
                id="new-001",
                title="New Article",
                url="https://example.com/new",
                source_url=None,
                author=None,
                source=None,
                category=None,
                location=None,
                site_name=None,
                word_count=None,
                reading_time=None,
                created_at=now,
                updated_at=now,
                published_date=None,
                summary=None,
                image_url=None,
                notes=None,
                reading_progress=None,
            ),
            Article(
                id="old-001",
                title="Old Article",
                url="https://example.com/old",
                source_url=None,
                author=None,
                source=None,
                category=None,
                location=None,
                site_name=None,
                word_count=None,
                reading_time=None,
                created_at=old_time,
                updated_at=old_time,
                published_date=None,
                summary=None,
                image_url=None,
                notes=None,
                reading_progress=None,
            ),
        ]

        result = filter_articles(articles, hours=24, max_candidates=10)

        assert len(result) == 1
        assert result[0].id == "new-001"

    def test_filter_articles_dedupe_by_url(self) -> None:
        """Test duplicate articles are removed."""
        now = datetime.now(timezone.utc)

        articles = [
            Article(
                id="dup-001",
                title="First Article",
                url="https://example.com/article",
                source_url="https://example.com/original",
                author=None,
                source=None,
                category=None,
                location=None,
                site_name=None,
                word_count=None,
                reading_time=None,
                created_at=now,
                updated_at=now,
                published_date=None,
                summary=None,
                image_url=None,
                notes=None,
                reading_progress=None,
            ),
            Article(
                id="dup-002",
                title="Duplicate Article",
                url="https://example.com/article-2",
                source_url="https://example.com/original",  # Same source_url
                author=None,
                source=None,
                category=None,
                location=None,
                site_name=None,
                word_count=None,
                reading_time=None,
                created_at=now - timedelta(minutes=5),
                updated_at=now - timedelta(minutes=5),
                published_date=None,
                summary=None,
                image_url=None,
                notes=None,
                reading_progress=None,
            ),
        ]

        result = filter_articles(articles, hours=24, max_candidates=10)

        # Should keep only one, preferring the more recently updated
        assert len(result) == 1
        assert result[0].id == "dup-001"  # More recent

    def test_filter_articles_excludes_parent_documents(self) -> None:
        """Test articles with parent_id are excluded."""
        now = datetime.now(timezone.utc)

        articles = [
            Article(
                id="parent-001",
                title="Parent Article",
                url="https://example.com/parent",
                source_url=None,
                author=None,
                source=None,
                category=None,
                location=None,
                site_name=None,
                word_count=None,
                reading_time=None,
                created_at=now,
                updated_at=now,
                published_date=None,
                summary=None,
                image_url=None,
                notes=None,
                reading_progress=None,
                parent_id=None,
            ),
            Article(
                id="child-001",
                title="Child Highlight",
                url="https://example.com/highlight",
                source_url=None,
                author=None,
                source=None,
                category="highlight",
                location=None,
                site_name=None,
                word_count=None,
                reading_time=None,
                created_at=now,
                updated_at=now,
                published_date=None,
                summary=None,
                image_url=None,
                notes=None,
                reading_progress=None,
                parent_id="parent-001",  # Has parent
            ),
        ]

        result = filter_articles(articles, hours=24, max_candidates=10)

        assert len(result) == 1
        assert result[0].id == "parent-001"

    def test_filter_articles_excludes_empty_titles(self) -> None:
        """Test articles with empty titles are excluded."""
        now = datetime.now(timezone.utc)

        articles = [
            Article(
                id="valid-001",
                title="Valid Title",
                url="https://example.com/valid",
                source_url=None,
                author=None,
                source=None,
                category=None,
                location=None,
                site_name=None,
                word_count=None,
                reading_time=None,
                created_at=now,
                updated_at=now,
                published_date=None,
                summary=None,
                image_url=None,
                notes=None,
                reading_progress=None,
            ),
            Article(
                id="invalid-001",
                title="",  # Empty title
                url="https://example.com/invalid",
                source_url=None,
                author=None,
                source=None,
                category=None,
                location=None,
                site_name=None,
                word_count=None,
                reading_time=None,
                created_at=now,
                updated_at=now,
                published_date=None,
                summary=None,
                image_url=None,
                notes=None,
                reading_progress=None,
            ),
        ]

        result = filter_articles(articles, hours=24, max_candidates=10)

        assert len(result) == 1
        assert result[0].id == "valid-001"

    def test_filter_articles_respects_max_candidates(self, sample_articles_list: list[Article]) -> None:
        """Test max_candidates limit is respected."""
        result = filter_articles(
            sample_articles_list,
            hours=24,
            max_candidates=3,
        )

        assert len(result) == 3
