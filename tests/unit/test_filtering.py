"""Unit tests for article filtering pipeline."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from src.models import Article
from src.pipeline.filtering import filter_articles, select_diverse_candidates
from src.pipeline.source_taxonomy import publisher_key, topic_for


def _mk_article(
    *,
    article_id: str,
    title: str = "x",
    site_name: str | None = None,
    source: str | None = None,
    author: str | None = None,
    category: str | None = None,
    canonical_url: str = "https://example.com/x",
    created_minutes_ago: int = 0,
    published_date: date | None = None,
    tags: list[str] | None = None,
) -> Article:
    base_time = datetime.now(timezone.utc) - timedelta(minutes=created_minutes_ago)
    return Article(
        id=article_id,
        title=title,
        url=canonical_url,
        source_url=canonical_url,
        author=author,
        source=source,
        category=category,
        location="feed",
        site_name=site_name,
        word_count=None,
        reading_time=None,
        created_at=base_time,
        updated_at=base_time,
        published_date=published_date,
        summary=None,
        image_url=None,
        notes=None,
        reading_progress=None,
        tags=tags or [],
    )


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

    def test_filter_articles_excludes_stale_published_date(self) -> None:
        today = datetime.now(timezone.utc).date()
        articles = [
            _mk_article(
                article_id="fresh",
                canonical_url="https://example.com/fresh",
                published_date=today - timedelta(days=2),
            ),
            _mk_article(
                article_id="stale",
                canonical_url="https://example.com/stale",
                published_date=today - timedelta(days=20),
            ),
            _mk_article(
                article_id="unknown-date",
                canonical_url="https://example.com/unknown",
                published_date=None,
            ),
        ]

        result = filter_articles(
            articles,
            hours=24,
            max_candidates=10,
            max_published_age_days=7,
        )

        assert {item.id for item in result} == {"fresh", "unknown-date"}

    def test_filter_articles_excludes_stale_title_date(self) -> None:
        articles = [
            _mk_article(
                article_id="fresh",
                title="每日安全动态推送(26/5/10)",
                canonical_url="https://example.com/fresh-title",
            ),
            _mk_article(
                article_id="stale",
                title="每日安全动态推送(26/3/3)",
                canonical_url="https://example.com/stale-title",
            ),
        ]

        result = filter_articles(
            articles,
            hours=24,
            max_candidates=10,
            max_published_age_days=7,
        )

        assert [item.id for item in result] == ["fresh"]

    def test_filter_articles_excludes_email_noise(self) -> None:
        articles = [
            _mk_article(
                article_id="content-1",
                title="Import AI 456: RSI and economic growth",
                category="email",
                author="Jack Clark from Import AI",
                canonical_url="https://example.com/content-1",
            ),
            _mk_article(
                article_id="content-2",
                title="👀 Hermes Agent is the next big thing for devs",
                category="email",
                author="The Code",
                canonical_url="https://example.com/content-2",
            ),
            _mk_article(
                article_id="noise-welcome",
                title="Welcome to Import AI",
                category="email",
                author="Jack Clark from Import AI",
                canonical_url="https://example.com/welcome",
            ),
            _mk_article(
                article_id="noise-subscribe",
                title="Thanks for Subscribing",
                category="email",
                author="The Code",
                canonical_url="https://example.com/subscribe",
            ),
            _mk_article(
                article_id="noise-code",
                title="450829 is your Substack verification code",
                category="email",
                author="ben's bites",
                canonical_url="https://example.com/code",
            ),
            _mk_article(
                article_id="noise-official",
                title="You're officially Superhuman 🤖",
                category="email",
                author="Superhuman – Zain Kahn",
                canonical_url="https://example.com/official",
            ),
            _mk_article(
                article_id="noise-treats",
                title="😺 We've got AI treats for you...",
                category="email",
                author="The Neuron",
                canonical_url="https://example.com/treats",
            ),
        ]

        result = filter_articles(articles, hours=24, max_candidates=10)

        assert {item.id for item in result} == {"content-1", "content-2"}

    def test_email_noise_filter_does_not_apply_to_rss(self) -> None:
        article = _mk_article(
            article_id="rss",
            title="Thanks for Subscribing",
            category="rss",
            canonical_url="https://example.com/rss",
        )

        result = filter_articles([article], hours=24, max_candidates=10)

        assert [item.id for item in result] == ["rss"]

    def test_select_diverse_candidates_balances_authors_when_source_same(self) -> None:
        """Test author diversity is preferred when all articles share one source."""
        now = datetime.now(timezone.utc)
        articles = [
            Article(
                id=f"article-{index}",
                title=f"Article {index}",
                url=f"https://example.com/{index}",
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
                summary=None,
                image_url=None,
                notes=None,
                reading_progress=None,
            )
            for index, author in enumerate(
                ["Author A", "Author A", "Author A", "Author B", "Author B", "Author C"],
                start=1,
            )
        ]

        result = select_diverse_candidates(articles, max_candidates=3)

        assert len(result) == 3
        assert {item.author for item in result} == {"Author A", "Author B", "Author C"}

    def test_select_diverse_candidates_balances_sources_before_reusing_source(self) -> None:
        """Test source diversity is preferred when authors are missing."""
        now = datetime.now(timezone.utc)
        articles = [
            Article(
                id=f"article-{index}",
                title=f"Article {index}",
                url=f"https://{site}.example.com/{index}",
                source_url=None,
                author=None,
                source=site,
                category="article",
                location="feed",
                site_name=site,
                word_count=None,
                reading_time=None,
                created_at=now - timedelta(minutes=index),
                updated_at=now - timedelta(minutes=index),
                published_date=None,
                summary=None,
                image_url=None,
                notes=None,
                reading_progress=None,
            )
            for index, site in enumerate(
                ["Site A", "Site A", "Site B", "Site B", "Site C"],
                start=1,
            )
        ]

        result = select_diverse_candidates(articles, max_candidates=3)

        assert len(result) == 3
        assert {item.site_name for item in result} == {"Site A", "Site B", "Site C"}

    def test_select_diverse_candidates_preserves_recency_inside_same_bucket(self) -> None:
        """Test more recent articles win when source and author are identical."""
        now = datetime.now(timezone.utc)
        articles = [
            Article(
                id=f"article-{index}",
                title=f"Article {index}",
                url=f"https://example.com/{index}",
                source_url=None,
                author="Same Author",
                source="Same Source",
                category="article",
                location="feed",
                site_name="Same Site",
                word_count=None,
                reading_time=None,
                created_at=now - timedelta(minutes=index),
                updated_at=now - timedelta(minutes=index),
                published_date=None,
                summary=None,
                image_url=None,
                notes=None,
                reading_progress=None,
            )
            for index in range(1, 5)
        ]

        result = select_diverse_candidates(articles, max_candidates=2)

        assert [item.id for item in result] == ["article-1", "article-2"]


class TestTopicKey:
    """Tests for source_taxonomy.topic_for."""

    @pytest.mark.parametrize(
        "site_name, expected",
        [
            ("量子位", "ai"),
            ("新智元", "ai"),
            ("机器之心", "ai"),
            ("奇安信威胁情报中心", "security"),
            ("安全内参", "security"),
            ("阿里云开发者", "infra"),
            ("MIT Technology Review", "research"),
            ("The Berkeley Artificial Intelligence Research", "research"),
            ("The Verge - Artificial Intelligences", "ai"),
        ],
    )
    def test_topic_key_maps_known_sites(self, site_name: str, expected: str) -> None:
        article = _mk_article(article_id="x", site_name=site_name)
        assert topic_for(article) == expected

    def test_topic_key_substack_newsletter_maps_to_business(self) -> None:
        article = _mk_article(
            article_id="x",
            site_name="Import AI",
            author="Jack Clark",
            canonical_url="https://importai.substack.com/p/abc",
        )
        assert topic_for(article) == "business"

    def test_topic_key_email_category_falls_back_to_business(self) -> None:
        article = _mk_article(article_id="x", site_name="Some random list", category="email")
        assert topic_for(article) == "business"

    def test_topic_key_falls_back_to_other_for_unknown_site(self) -> None:
        article = _mk_article(article_id="x", site_name="Some Random Blog")
        assert topic_for(article) == "other"

    def test_topic_key_uses_title_keywords_when_site_unknown(self) -> None:
        article = _mk_article(article_id="x", site_name="Random Blog", title="新型 LLM 的 RAG 优化")
        assert topic_for(article) == "ai"

    def test_topic_key_respects_allowed_topics_whitelist(self) -> None:
        article = _mk_article(article_id="x", site_name="量子位")  # would be "ai"
        assert topic_for(article, allowed_topics=["security", "other"]) == "other"


class TestPublisherKey:
    """Tests for source_taxonomy.publisher_key."""

    def test_uses_site_name_for_normal_sources(self) -> None:
        article = _mk_article(article_id="x", site_name="MIT Technology Review", author="Will Knight")
        assert publisher_key(article) == "mit technology review"

    def test_falls_back_to_author_when_site_is_aggregator(self) -> None:
        article = _mk_article(
            article_id="x",
            site_name="Weixin Official Accounts Platform",
            author="腾讯玄武实验室",
        )
        assert publisher_key(article) == "腾讯玄武实验室"

    def test_substack_aggregator_falls_back_to_author(self) -> None:
        article = _mk_article(
            article_id="x",
            site_name="Substack",
            author="Jack Clark",
            canonical_url="https://importai.substack.com/p/x",
        )
        assert publisher_key(article) == "jack clark"

    def test_falls_back_to_hostname_when_everything_is_missing(self) -> None:
        article = _mk_article(
            article_id="x",
            site_name=None,
            author=None,
            source=None,
            canonical_url="https://example.com/x",
        )
        assert publisher_key(article) == "example.com"


class TestSelectDiverseCandidatesTopicAware:
    """Tests for the new topic dimension in select_diverse_candidates."""

    def test_balances_topics_across_known_sites(self) -> None:
        """When asked for 6, expect 2 articles from each of 3 topics."""
        articles: list[Article] = []
        for index in range(10):
            articles.append(
                _mk_article(
                    article_id=f"ai-{index}",
                    site_name="量子位",
                    author=f"qbit-{index}",
                    canonical_url=f"https://qbit.example.com/{index}",
                    created_minutes_ago=index,
                )
            )
        for index in range(10):
            articles.append(
                _mk_article(
                    article_id=f"sec-{index}",
                    site_name="奇安信威胁情报中心",
                    author=f"qax-{index}",
                    canonical_url=f"https://qax.example.com/{index}",
                    created_minutes_ago=200 + index,
                )
            )
        for index in range(10):
            articles.append(
                _mk_article(
                    article_id=f"news-{index}",
                    site_name="Import AI",
                    author="Jack Clark",
                    canonical_url=f"https://importai.substack.com/{index}",
                    category="email",
                    created_minutes_ago=400 + index,
                )
            )

        selected = select_diverse_candidates(articles, max_candidates=6)
        topics = [topic_for(a) for a in selected]
        assert topics.count("ai") == 2
        assert topics.count("security") == 2
        assert topics.count("business") == 2

    def test_diversity_uses_author_when_site_is_aggregator(self) -> None:
        """WeChat-style: site_name shared, author distinguishes publication."""
        articles = [
            _mk_article(
                article_id=f"wx-a-{i}",
                site_name="Weixin Official Accounts Platform",
                author="腾讯玄武实验室",
                canonical_url=f"https://mp.weixin.qq.com/a/{i}",
                created_minutes_ago=i,
            )
            for i in range(3)
        ] + [
            _mk_article(
                article_id=f"wx-b-{i}",
                site_name="Weixin Official Accounts Platform",
                author="奇安信威胁情报中心",
                canonical_url=f"https://mp.weixin.qq.com/b/{i}",
                created_minutes_ago=10 + i,
            )
            for i in range(3)
        ]

        selected = select_diverse_candidates(articles, max_candidates=4)
        # The two distinct publishers should each get represented before any
        # publisher gets a 3rd slot.
        publishers = [publisher_key(a) for a in selected]
        assert publishers.count("腾讯玄武实验室") == 2
        assert publishers.count("奇安信威胁情报中心") == 2

    def test_allowed_topics_collapses_excluded_to_other(self) -> None:
        """When ai is excluded from whitelist, ai-articles compete in 'other' bucket."""
        articles = [
            _mk_article(
                article_id=f"ai-{i}",
                site_name="量子位",
                author=f"qbit-{i}",
                canonical_url=f"https://qbit.example.com/{i}",
                created_minutes_ago=i,
            )
            for i in range(4)
        ] + [
            _mk_article(
                article_id="sec-1",
                site_name="奇安信威胁情报中心",
                author="qax",
                canonical_url="https://qax.example.com/1",
                created_minutes_ago=100,
            ),
        ]
        selected = select_diverse_candidates(
            articles, max_candidates=2, allowed_topics=["security", "other"]
        )
        ids = [a.id for a in selected]
        assert "sec-1" in ids
        # The second pick is whichever ai article is most recent (now bucketed as "other")
        assert any(i.startswith("ai-") for i in ids)
