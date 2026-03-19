"""Unit tests for article ranking pipeline."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.clients.llm_client import LLMClient
from src.models import Article, ScoredArticle
from src.pipeline.ranking import _build_article_payload, _truncate_text, score_articles


class TestRankingUtilities:
    """Tests for ranking utility functions."""

    def test_truncate_text_within_limit(self) -> None:
        """Test text within limit is not truncated."""
        text = "Short text"
        result = _truncate_text(text, 100)
        assert result == "Short text"

    def test_truncate_text_exceeds_limit(self) -> None:
        """Test text exceeding limit is truncated."""
        text = "This is a very long text that should be truncated"
        result = _truncate_text(text, 20)
        assert len(result) <= 20
        assert result.endswith("...")

    def test_build_article_payload(self) -> None:
        """Test article payload building."""
        article = Article(
            id="test-001",
            title="Test Article",
            url="https://example.com/article",
            source_url="https://original.com/article",
            author="Test Author",
            source="Test Source",
            category="article",
            location="new",
            site_name="Test Site",
            word_count=1000,
            reading_time="5 mins",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            published_date=None,
            summary="Readwise summary",
            image_url=None,
            notes=None,
            reading_progress=0.5,
            text_content="This is the article text content for testing.",
        )

        payload = _build_article_payload(article, max_input_chars=1000)

        assert "Test Article" in payload
        assert "Test Site" in payload
        assert "Test Author" in payload
        assert "https://original.com/article" in payload
        assert "Readwise summary" in payload


class TestLLMClientExtractJson:
    """Tests for LLMClient._extract_json static method."""

    def test_extract_json_with_fenced_code_block(self) -> None:
        """Test extracting JSON from fenced code block."""
        content = 'Some text\n```json\n{"score": 85}\n```\nMore text'
        result = LLMClient._extract_json(content)
        assert result == {"score": 85}

    def test_extract_json_plain(self) -> None:
        """Test extracting plain JSON."""
        content = '{"overall_score": 90, "summary": "Great article"}'
        result = LLMClient._extract_json(content)
        assert result["overall_score"] == 90
        assert result["summary"] == "Great article"

    def test_extract_json_invalid_raises_error(self) -> None:
        """Test invalid JSON raises ValueError."""
        content = "Not valid JSON"
        with pytest.raises(ValueError) as exc_info:
            LLMClient._extract_json(content)
        assert "does not contain valid JSON" in str(exc_info.value)


class TestScoreArticles:
    """Tests for the score_articles function."""

    def test_score_articles_success(self, sample_articles_list: list[Article]) -> None:
        """Test successful scoring of articles."""
        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.chat_json.return_value = {
            "overall_score": 85,
            "relevance_score": 90,
            "novelty_score": 80,
            "actionability_score": 85,
            "summary": "Generated summary",
            "recommendation": "Recommended",
            "keywords": ["AI", "tech"],
        }

        result = score_articles(
            sample_articles_list[:2],
            llm_client=mock_llm,
            max_input_chars=1000,
            digest_language="中文",
            scoring_focus="Test focus",
            top_n=2,
        )

        assert len(result) == 2
        assert all(isinstance(item, ScoredArticle) for item in result)
        assert result[0].overall_score == 85
        assert result[0].summary == "Generated summary"

    def test_score_articles_sorts_by_score(self, sample_articles_list: list[Article]) -> None:
        """Test articles are sorted by overall score descending."""
        mock_llm = MagicMock(spec=LLMClient)

        # Return different scores for different articles
        scores = [70, 95, 60, 88, 75]
        def side_effect(*, system_prompt, user_prompt):
            idx = mock_llm.chat_json.call_count - 1
            return {
                "overall_score": scores[idx],
                "relevance_score": 80,
                "novelty_score": 70,
                "actionability_score": 75,
                "summary": f"Summary {idx}",
                "recommendation": f"Rec {idx}",
                "keywords": ["test"],
            }

        mock_llm.chat_json.side_effect = side_effect

        result = score_articles(
            sample_articles_list,
            llm_client=mock_llm,
            max_input_chars=1000,
            digest_language="中文",
            scoring_focus="Test focus",
            top_n=5,
        )

        # Should be sorted by overall_score descending
        scores_result = [item.overall_score for item in result]
        assert scores_result == sorted(scores, reverse=True)

    def test_score_articles_respects_top_n(self, sample_articles_list: list[Article]) -> None:
        """Test top_n limit is respected."""
        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.chat_json.return_value = {
            "overall_score": 80,
            "relevance_score": 80,
            "novelty_score": 80,
            "actionability_score": 80,
            "summary": "Summary",
            "recommendation": "Rec",
            "keywords": [],
        }

        result = score_articles(
            sample_articles_list,
            llm_client=mock_llm,
            max_input_chars=1000,
            digest_language="中文",
            scoring_focus="Test focus",
            top_n=3,
        )

        assert len(result) == 3

    def test_score_articles_fallback_on_error(self) -> None:
        """Test fallback values on LLM error."""
        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.chat_json.side_effect = Exception("LLM API Error")

        # Create article without summary to test full fallback behavior
        from datetime import datetime, timezone
        article_without_summary = Article(
            id="test-fallback",
            title="Fallback Test Article",
            url="https://example.com/fallback",
            source_url=None,
            author=None,
            source=None,
            category=None,
            location=None,
            site_name=None,
            word_count=None,
            reading_time=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            published_date=None,
            summary=None,  # No summary
            image_url=None,
            notes=None,
            reading_progress=None,
        )

        result = score_articles(
            [article_without_summary],
            llm_client=mock_llm,
            max_input_chars=1000,
            digest_language="中文",
            scoring_focus="Test focus",
            top_n=1,
        )

        assert len(result) == 1
        assert result[0].overall_score == 50  # Default fallback
        assert "LLM 评分失败" in result[0].summary
