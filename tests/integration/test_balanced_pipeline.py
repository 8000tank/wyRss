"""Integration test: balanced pipeline with mixed sources.

Drives the full filter -> diversity -> score -> apply_diversity chain on a
deterministic mix of articles and asserts the final selection is balanced
across topics and sites. No external API calls.
"""
from __future__ import annotations

import json
import threading
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

from src.models import Article
from src.pipeline.filtering import filter_articles, select_diverse_candidates
from src.pipeline.ranking import score_articles
from src.pipeline.source_taxonomy import topic_for


_AI_SITES = ["量子位", "新智元", "机器之心"]
_SECURITY_SITES = ["奇安信威胁情报中心", "安全内参", "腾讯玄武实验室"]
_NEWSLETTERS = [
    ("Import AI", "Jack Clark", "https://importai.substack.com"),
    ("Ben's Bites", "Ben", "https://bensbites.substack.com"),
    ("The Neuron", "Grant", "https://theneuron.substack.com"),
]


def _build_mixed_pool() -> list[Article]:
    """Construct 80 ai + 30 security + 10 newsletter articles, all within 24h."""
    now = datetime.now(timezone.utc)
    articles: list[Article] = []

    for index in range(80):
        site = _AI_SITES[index % len(_AI_SITES)]
        articles.append(
            Article(
                id=f"ai-{index:03d}",
                title=f"AI 新闻 {index}",
                url=f"https://ai{index}.example.com/{index}",
                source_url=f"https://ai{index}.example.com/{index}",
                author=f"{site}-author-{index}",
                source="Weixin",
                category="rss",
                location="feed",
                site_name=site,
                word_count=1500,
                reading_time="5 mins",
                created_at=now - timedelta(minutes=index),
                updated_at=now - timedelta(minutes=index),
                published_date=None,
                summary=f"AI 摘要 {index}",
                image_url=None,
                notes=None,
                reading_progress=None,
                text_content=f"AI 正文 {index}",
            )
        )

    for index in range(30):
        site = _SECURITY_SITES[index % len(_SECURITY_SITES)]
        articles.append(
            Article(
                id=f"sec-{index:03d}",
                title=f"安全公告 {index}",
                url=f"https://sec{index}.example.com/{index}",
                source_url=f"https://sec{index}.example.com/{index}",
                author=f"{site}-author-{index}",
                source="Weixin",
                category="rss",
                location="feed",
                site_name=site,
                word_count=2000,
                reading_time="7 mins",
                created_at=now - timedelta(minutes=200 + index),
                updated_at=now - timedelta(minutes=200 + index),
                published_date=None,
                summary=f"安全摘要 {index}",
                image_url=None,
                notes=None,
                reading_progress=None,
                text_content=f"安全正文 {index}",
            )
        )

    for index in range(10):
        site, author, base_url = _NEWSLETTERS[index % len(_NEWSLETTERS)]
        articles.append(
            Article(
                id=f"news-{index:03d}",
                title=f"Newsletter {index}",
                url=f"{base_url}/p/{index}",
                source_url=f"{base_url}/p/{index}",
                author=author,
                source="Substack",
                category="email",
                location="feed",
                site_name=site,
                word_count=4000,
                reading_time="20 mins",
                created_at=now - timedelta(minutes=400 + index),
                updated_at=now - timedelta(minutes=400 + index),
                published_date=None,
                summary=f"Newsletter summary {index}",
                image_url=None,
                notes=None,
                reading_progress=None,
                text_content=f"Newsletter long body {index}",
            )
        )

    return articles


class _DeterministicLLM:
    """Returns a fixed all-80 score so ordering is decided purely by tie-breakers."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.calls: list[str] = []
        self.active = 0
        self.max_active = 0

    def chat(self, *, system_prompt: str, user_prompt: str) -> str:
        with self.lock:
            self.calls.append(user_prompt)
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        time.sleep(0.005)
        with self.lock:
            self.active -= 1
        return json.dumps(
            {
                "overall_score": 80,
                "relevance_score": 80,
                "novelty_score": 80,
                "actionability_score": 80,
                "summary": "ok",
                "recommendation": "ok",
                "keywords": ["k"],
            }
        )


class TestBalancedPipeline:
    def test_full_pipeline_keeps_newsletter_and_security(self) -> None:
        allowed_topics = ["ai", "security", "infra", "research", "business", "other"]

        pool = _build_mixed_pool()
        assert len(pool) == 120

        filtered = filter_articles(pool, hours=24, max_candidates=120)
        assert len(filtered) == 120

        pre_scored = select_diverse_candidates(
            filtered,
            max_candidates=30,
            allowed_topics=allowed_topics,
        )
        assert len(pre_scored) == 30

        # Pre-score pool must already span at least 3 topics, with newsletter
        # and security represented.
        pre_topics = Counter(topic_for(a, allowed_topics) for a in pre_scored)
        assert pre_topics["ai"] > 0
        assert pre_topics["security"] > 0
        assert pre_topics["business"] > 0
        assert len(pre_topics) >= 3

        llm = _DeterministicLLM()
        scored = score_articles(
            pre_scored,
            llm_client=llm,
            max_input_chars=2000,
            digest_language="中文",
            scoring_focus="balanced",
            top_n=12,
            llm_concurrency=2,
            max_per_site=2,
            max_per_author=2,
        )

        assert len(llm.calls) == 30
        # Concurrency was honoured.
        assert llm.max_active >= 2
        # All scoring prompts carry the content_type label.
        assert all("内容类型:" in prompt for prompt in llm.calls)
        # At least one newsletter prompt actually flagged "newsletter".
        assert any("内容类型: newsletter" in prompt for prompt in llm.calls)

        assert len(scored) == 12

        final_articles = [s.article for s in scored]
        final_topics = Counter(topic_for(a, allowed_topics) for a in final_articles)
        final_sites = Counter(a.site_name or "?" for a in final_articles)

        # Step 1 success: newsletter survived to the final cut.
        assert final_topics["business"] >= 1, f"newsletter dropped, topics={final_topics}"
        # Step 4 success: security survived too.
        assert final_topics["security"] >= 1, f"security dropped, topics={final_topics}"
        # Step 4 success: at least 3 distinct topics in the final cut.
        assert len(final_topics) >= 3, f"too few topics, topics={final_topics}"
        # Step 2 success: no single site exceeds max_per_site=2.
        offending = {site: count for site, count in final_sites.items() if count > 2}
        assert not offending, f"site cap violated: {offending}"
