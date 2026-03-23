"""Integration tests for pre-score diversity selection in the digest pipeline."""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone

from src.models import Article
from src.pipeline.filtering import filter_articles, select_diverse_candidates
from src.pipeline.ranking import score_articles


class _FakeLLMClient:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.lock = threading.Lock()
        self.active_calls = 0
        self.max_active_calls = 0

    def chat_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, object]:
        with self.lock:
            self.calls.append(user_prompt)
            self.active_calls += 1
            self.max_active_calls = max(self.max_active_calls, self.active_calls)

        time.sleep(0.02)

        with self.lock:
            self.active_calls -= 1

        return {
            "overall_score": 80,
            "relevance_score": 80,
            "novelty_score": 80,
            "actionability_score": 80,
            "summary": "test summary",
            "recommendation": "test recommendation",
            "keywords": ["test"],
        }


class TestDiverseCandidatePipeline:
    def test_diverse_selection_reduces_llm_calls_before_scoring(self) -> None:
        """Pipeline should score only the pre-selected diverse subset."""
        now = datetime.now(timezone.utc)
        articles: list[Article] = []

        for index in range(50):
            author = f"Author {index % 10}"
            articles.append(
                Article(
                    id=f"article-{index}",
                    title=f"Article {index}",
                    url=f"https://example.com/article-{index}",
                    source_url=None,
                    author=author,
                    source="Weixin Official Accounts Platform",
                    category="article",
                    location="feed",
                    site_name="Weixin Official Accounts Platform",
                    word_count=None,
                    reading_time=None,
                    created_at=now - timedelta(minutes=index),
                    updated_at=now - timedelta(minutes=index),
                    published_date=None,
                    summary=f"Summary {index}",
                    image_url=None,
                    notes=None,
                    reading_progress=None,
                    text_content=f"Content {index}",
                )
            )

        filtered = filter_articles(articles, hours=24, max_candidates=50)
        pre_scored = select_diverse_candidates(filtered, max_candidates=20)

        llm_client = _FakeLLMClient()
        scored = score_articles(
            pre_scored,
            llm_client=llm_client,
            max_input_chars=6000,
            digest_language="中文",
            scoring_focus="信息价值优先",
            top_n=10,
            llm_concurrency=2,
        )

        assert len(filtered) == 50
        assert len(pre_scored) == 20
        assert len(llm_client.calls) == 20
        assert llm_client.max_active_calls >= 2
        assert len({article.author for article in pre_scored}) == 10
        assert len(scored) == 10
