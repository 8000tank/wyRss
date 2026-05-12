"""Unit tests for ReadwiseClient bucket fetching."""
from __future__ import annotations

from typing import Any

import pytest
import responses

from src.clients.readwise_client import ReadwiseClient
from src.config import FetchBucket


def _doc(doc_id: str, *, category: str, source_url: str | None = None) -> dict[str, Any]:
    """Build a minimal Readwise document payload."""
    return {
        "id": doc_id,
        "title": f"Title {doc_id}",
        "url": f"https://read.readwise.io/read/{doc_id}",
        "source_url": source_url or f"https://example.com/{doc_id}",
        "author": f"Author-{doc_id[0]}",
        "source": "stub",
        "category": category,
        "location": "feed",
        "site_name": f"Site-{doc_id[0]}",
        "word_count": 1000,
        "reading_time": "4 mins",
        "created_at": "2026-05-01T00:00:00Z",
        "updated_at": "2026-05-01T00:00:00Z",
        "published_date": None,
        "summary": "summary",
        "image_url": None,
        "notes": None,
        "reading_progress": 0.0,
        "tags": [],
        "html_content": "<p>x</p>",
    }


class TestListDocumentsByBuckets:
    """Tests for ReadwiseClient.list_documents_by_buckets."""

    @responses.activate
    def test_fetches_each_bucket_with_its_own_category(self) -> None:
        client = ReadwiseClient(token="t", base_url="https://api.example.com/v3")

        responses.get(
            "https://api.example.com/v3/list/",
            json={
                "results": [_doc("rss-1", category="rss"), _doc("rss-2", category="rss")],
                "nextPageCursor": None,
            },
            match=[responses.matchers.query_param_matcher({
                "limit": "100",
                "withHtmlContent": "true",
                "location": "feed",
                "category": "rss",
            })],
        )
        responses.get(
            "https://api.example.com/v3/list/",
            json={
                "results": [_doc("email-1", category="email")],
                "nextPageCursor": None,
            },
            match=[responses.matchers.query_param_matcher({
                "limit": "100",
                "withHtmlContent": "true",
                "location": "feed",
                "category": "email",
            })],
        )

        result = client.list_documents_by_buckets(
            [FetchBucket(category="rss", max_items=60), FetchBucket(category="email", max_items=20)],
            location="feed",
        )

        ids = sorted(article.id for article in result)
        assert ids == ["email-1", "rss-1", "rss-2"]

    @responses.activate
    def test_deduplicates_articles_by_id_across_buckets(self) -> None:
        client = ReadwiseClient(token="t", base_url="https://api.example.com/v3")

        # Same id appears in both buckets (e.g. category=None overlaps with category=rss).
        shared_doc = _doc("dup-1", category="rss")
        responses.get(
            "https://api.example.com/v3/list/",
            json={"results": [shared_doc], "nextPageCursor": None},
            match=[responses.matchers.query_param_matcher({
                "limit": "100",
                "withHtmlContent": "true",
                "category": "rss",
            })],
        )
        responses.get(
            "https://api.example.com/v3/list/",
            json={
                "results": [shared_doc, _doc("only-2", category="article")],
                "nextPageCursor": None,
            },
            match=[responses.matchers.query_param_matcher({
                "limit": "100",
                "withHtmlContent": "true",
            })],
        )

        result = client.list_documents_by_buckets(
            [FetchBucket(category="rss", max_items=5), FetchBucket(category=None, max_items=5)],
        )

        ids = sorted(article.id for article in result)
        assert ids == ["dup-1", "only-2"]

    @responses.activate
    def test_respects_per_bucket_max_items(self) -> None:
        client = ReadwiseClient(token="t", base_url="https://api.example.com/v3")

        # Bucket should stop after max_items=2 even if more results were available.
        responses.get(
            "https://api.example.com/v3/list/",
            json={
                "results": [
                    _doc("a", category="rss"),
                    _doc("b", category="rss"),
                    _doc("c", category="rss"),
                ],
                "nextPageCursor": None,
            },
        )

        result = client.list_documents_by_buckets([FetchBucket(category="rss", max_items=2)])

        assert len(result) == 2
        assert sorted(a.id for a in result) == ["a", "b"]

    @responses.activate
    def test_bucket_location_overrides_global_location(self) -> None:
        client = ReadwiseClient(token="t", base_url="https://api.example.com/v3")

        responses.get(
            "https://api.example.com/v3/list/",
            json={
                "results": [_doc("rss-1", category="rss")],
                "nextPageCursor": None,
            },
            match=[responses.matchers.query_param_matcher({
                "limit": "100",
                "withHtmlContent": "true",
                "location": "feed",
                "category": "rss",
            })],
        )
        responses.get(
            "https://api.example.com/v3/list/",
            json={
                "results": [_doc("email-1", category="email")],
                "nextPageCursor": None,
            },
            match=[responses.matchers.query_param_matcher({
                "limit": "100",
                "withHtmlContent": "true",
                "location": "new",
                "category": "email",
            })],
        )

        result = client.list_documents_by_buckets(
            [
                FetchBucket(category="rss", location="feed", max_items=60),
                FetchBucket(category="email", location="new", max_items=20),
            ],
            location="feed",
        )

        ids = sorted(article.id for article in result)
        assert ids == ["email-1", "rss-1"]

    @responses.activate
    def test_empty_buckets_returns_empty_list_with_no_calls(self) -> None:
        client = ReadwiseClient(token="t", base_url="https://api.example.com/v3")

        result = client.list_documents_by_buckets([])

        assert result == []
        assert len(responses.calls) == 0
