"""Unit tests for article ranking pipeline."""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.clients.llm_client import LLMClient
from src.models import Article, ScoredArticle
from src.pipeline.ranking import (
    _apply_author_diversity,
    _apply_diversity,
    _build_article_payload,
    _truncate_text,
    score_articles,
)


def _scored(
    *,
    article_id: str,
    site_name: str | None,
    author: str | None,
    overall: int,
    canonical_url: str | None = None,
) -> ScoredArticle:
    """Build a deterministic ScoredArticle for diversity tests."""
    url = canonical_url or f"https://{(site_name or 'site').lower().replace(' ', '-')}.example.com/{article_id}"
    article = Article(
        id=article_id,
        title=f"Title {article_id}",
        url=url,
        source_url=url,
        author=author,
        source=None,
        category=None,
        location=None,
        site_name=site_name,
        word_count=None,
        reading_time=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        published_date=None,
        summary=None,
        image_url=None,
        notes=None,
        reading_progress=None,
    )
    return ScoredArticle(
        article=article,
        overall_score=overall,
        relevance_score=overall,
        novelty_score=overall,
        actionability_score=overall,
        summary="s",
        recommendation="r",
        keywords=[],
        raw_response="ok",
    )


def _llm_returning(payload: dict) -> MagicMock:
    """A MagicMock LLMClient whose .chat() returns a JSON string of payload."""
    import json as _json

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.chat.return_value = _json.dumps(payload)
    return mock_llm


class TestRankingUtilities:
    """Tests for ranking utility functions."""

    def test_truncate_text_within_limit(self) -> None:
        text = "Short text"
        result = _truncate_text(text, 100)
        assert result == "Short text"

    def test_truncate_text_exceeds_limit(self) -> None:
        text = "This is a very long text that should be truncated"
        result = _truncate_text(text, 20)
        assert len(result) <= 20
        assert result.endswith("...")

    def test_build_article_payload(self) -> None:
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
        # New: content type label is now part of every payload.
        assert "内容类型:" in payload


class TestLLMClientExtractJson:
    """Tests for LLMClient._extract_json static method."""

    def test_extract_json_with_fenced_code_block(self) -> None:
        content = 'Some text\n```json\n{"score": 85}\n```\nMore text'
        result = LLMClient._extract_json(content)
        assert result == {"score": 85}

    def test_extract_json_plain(self) -> None:
        content = '{"overall_score": 90, "summary": "Great article"}'
        result = LLMClient._extract_json(content)
        assert result["overall_score"] == 90
        assert result["summary"] == "Great article"

    def test_extract_json_invalid_raises_error(self) -> None:
        content = "Not valid JSON"
        with pytest.raises(ValueError) as exc_info:
            LLMClient._extract_json(content)
        # Production code wording.
        assert "Failed to parse LLM JSON response" in str(exc_info.value)


class TestScoreArticles:
    """Tests for the score_articles function."""

    def test_score_articles_success(self, sample_articles_list: list[Article]) -> None:
        mock_llm = _llm_returning({
            "overall_score": 85,
            "relevance_score": 90,
            "novelty_score": 80,
            "actionability_score": 85,
            "summary": "Generated summary",
            "recommendation": "Recommended",
            "keywords": ["AI", "tech"],
        })

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
        import json as _json

        mock_llm = MagicMock(spec=LLMClient)
        scores = [70, 95, 60, 88, 75]

        def side_effect(*, system_prompt, user_prompt):
            idx = mock_llm.chat.call_count - 1
            return _json.dumps({
                "overall_score": scores[idx],
                "relevance_score": 80,
                "novelty_score": 70,
                "actionability_score": 75,
                "summary": f"Summary {idx}",
                "recommendation": f"Rec {idx}",
                "keywords": ["test"],
            })

        mock_llm.chat.side_effect = side_effect

        result = score_articles(
            sample_articles_list,
            llm_client=mock_llm,
            max_input_chars=1000,
            digest_language="中文",
            scoring_focus="Test focus",
            top_n=5,
        )

        scores_result = [item.overall_score for item in result]
        assert scores_result == sorted(scores, reverse=True)

    def test_score_articles_respects_top_n(self, sample_articles_list: list[Article]) -> None:
        mock_llm = _llm_returning({
            "overall_score": 80,
            "relevance_score": 80,
            "novelty_score": 80,
            "actionability_score": 80,
            "summary": "Summary",
            "recommendation": "Rec",
            "keywords": [],
        })

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
        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.chat.side_effect = Exception("LLM API Error")

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
            summary=None,
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

    def test_score_articles_fallback_on_missing_required_field(
        self,
        sample_articles_list: list[Article],
    ) -> None:
        mock_llm = _llm_returning({
            "overall_score": 85,
            "relevance_score": 90,
            "actionability_score": 75,
            "summary": "Incomplete payload",
            "recommendation": "Should not be used",
            "keywords": [],
        })

        result = score_articles(
            sample_articles_list[:1],
            llm_client=mock_llm,
            max_input_chars=1000,
            digest_language="中文",
            scoring_focus="Test focus",
            top_n=1,
        )

        assert len(result) == 1
        assert result[0].overall_score == 50
        assert result[0].novelty_score == 50
        assert result[0].raw_response is None

    def test_score_articles_uses_configured_concurrency(self, sample_articles_list: list[Article]) -> None:
        import json as _json

        class SlowConcurrentLLMClient:
            def __init__(self) -> None:
                self.lock = threading.Lock()
                self.active_calls = 0
                self.max_active_calls = 0

            def chat(self, *, system_prompt, user_prompt):
                with self.lock:
                    self.active_calls += 1
                    self.max_active_calls = max(self.max_active_calls, self.active_calls)

                time.sleep(0.05)

                with self.lock:
                    self.active_calls -= 1

                return _json.dumps({
                    "overall_score": 80,
                    "relevance_score": 80,
                    "novelty_score": 80,
                    "actionability_score": 80,
                    "summary": "Summary",
                    "recommendation": "Rec",
                    "keywords": [],
                })

        llm_client = SlowConcurrentLLMClient()
        result = score_articles(
            sample_articles_list[:4],
            llm_client=llm_client,
            max_input_chars=1000,
            digest_language="中文",
            scoring_focus="Test focus",
            top_n=4,
            llm_concurrency=2,
        )

        assert len(result) == 4
        assert llm_client.max_active_calls >= 2

    def test_score_articles_fallback_on_error_with_concurrency(
        self,
        sample_articles_list: list[Article],
    ) -> None:
        import json as _json

        class PartiallyFailingLLMClient:
            def chat(self, *, system_prompt, user_prompt):
                if "Test Article 2" in user_prompt:
                    raise RuntimeError("simulated failure")
                return _json.dumps({
                    "overall_score": 80,
                    "relevance_score": 80,
                    "novelty_score": 80,
                    "actionability_score": 80,
                    "summary": "Summary",
                    "recommendation": "Rec",
                    "keywords": [],
                })

        result = score_articles(
            sample_articles_list[:3],
            llm_client=PartiallyFailingLLMClient(),
            max_input_chars=1000,
            digest_language="中文",
            scoring_focus="Test focus",
            top_n=3,
            llm_concurrency=2,
        )

        assert len(result) == 3
        fallback_items = [item for item in result if item.raw_response is None]
        assert len(fallback_items) == 1
        assert fallback_items[0].overall_score == 50

    def test_score_articles_passes_content_type_in_prompt(self) -> None:
        """Newsletter-typed articles must surface 'newsletter' inside the user prompt."""
        captured: list[str] = []

        class CapturingLLM:
            def chat(self, *, system_prompt, user_prompt):
                captured.append(user_prompt)
                import json as _json
                return _json.dumps({
                    "overall_score": 80,
                    "relevance_score": 80,
                    "novelty_score": 80,
                    "actionability_score": 80,
                    "summary": "s",
                    "recommendation": "r",
                    "keywords": [],
                })

        newsletter_article = Article(
            id="nl-1",
            title="Weekly Newsletter",
            url="https://importai.substack.com/p/x",
            source_url="https://importai.substack.com/p/x",
            author="Jack Clark",
            source="Substack",
            category="email",
            location="feed",
            site_name="Import AI",
            word_count=4000,
            reading_time="20 mins",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            published_date=None,
            summary="Long-form newsletter.",
            image_url=None,
            notes=None,
            reading_progress=None,
            text_content="long body",
        )

        score_articles(
            [newsletter_article],
            llm_client=CapturingLLM(),
            max_input_chars=1000,
            digest_language="中文",
            scoring_focus="x",
            top_n=1,
        )

        assert any("内容类型: newsletter" in prompt for prompt in captured)


class TestApplyDiversity:
    """Tests for the new dual-key (site + author) diversity helper."""

    def test_caps_per_site_keeps_top_two_per_site(self) -> None:
        scored = [
            _scored(article_id="a", site_name="Quanzi", author="A1", overall=99),
            _scored(article_id="b", site_name="Quanzi", author="A2", overall=98),
            _scored(article_id="c", site_name="Quanzi", author="A3", overall=97),
            _scored(article_id="d", site_name="MIT TR", author="B1", overall=80),
        ]
        kept = _apply_diversity(scored, max_per_site=2, max_per_author=99)
        ids = [item.article.id for item in kept]
        # Top 2 from Quanzi survive; the third is dropped; MIT TR still kept.
        assert ids == ["a", "b", "d"]

    def test_keeps_diverse_sites_over_higher_score_dups(self) -> None:
        """Even though Quanzi articles dominate scores, MIT TR survives once cap kicks in."""
        scored = [
            _scored(article_id="a", site_name="Quanzi", author="A1", overall=99),
            _scored(article_id="b", site_name="Quanzi", author="A2", overall=98),
            _scored(article_id="c", site_name="Quanzi", author="A3", overall=97),
            _scored(article_id="d", site_name="Quanzi", author="A4", overall=96),
            _scored(article_id="e", site_name="MIT TR", author="B1", overall=70),
        ]
        kept = _apply_diversity(scored, max_per_site=2, max_per_author=99)
        kept_ids = {item.article.id for item in kept}
        assert kept_ids == {"a", "b", "e"}

    def test_caps_per_author(self) -> None:
        scored = [
            _scored(article_id="a", site_name="X", author="Same", overall=99),
            _scored(article_id="b", site_name="Y", author="Same", overall=98),
            _scored(article_id="c", site_name="Z", author="Same", overall=97),
            _scored(article_id="d", site_name="W", author="Other", overall=50),
        ]
        kept = _apply_diversity(scored, max_per_site=99, max_per_author=2)
        ids = [item.article.id for item in kept]
        assert ids == ["a", "b", "d"]


class TestApplyAuthorDiversityAlias:
    """Backwards-compat: legacy helper name still works."""

    def test_apply_author_diversity_alias_still_works(self) -> None:
        scored = [
            _scored(article_id="a", site_name="X", author="Same", overall=99),
            _scored(article_id="b", site_name="X", author="Same", overall=98),
            _scored(article_id="c", site_name="X", author="Same", overall=97),
            _scored(article_id="d", site_name="X", author="Other", overall=50),
        ]
        # Site cap is effectively disabled inside the alias, so site grouping
        # does not interfere.
        kept = _apply_author_diversity(scored, max_per_author=2)
        ids = [item.article.id for item in kept]
        assert ids == ["a", "b", "d"]
