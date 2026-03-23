"""Unit tests for markdown renderer."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.models import Article, ScoredArticle
from src.renderers.markdown_renderer import (
    _escape_md_table_cell,
    _estimate_reading_time,
    _get_score_stars,
    render_markdown,
    write_markdown,
)


class TestUtilityFunctions:
    """Tests for helper functions."""

    def test_estimate_reading_time_with_word_count(self) -> None:
        """Test reading time estimation with word count."""
        assert _estimate_reading_time(300) == "1分钟"
        assert _estimate_reading_time(600) == "2分钟"
        assert _estimate_reading_time(1500) == "5分钟"

    def test_estimate_reading_time_without_word_count(self) -> None:
        """Test reading time estimation fallback."""
        assert _estimate_reading_time(None) == "2分钟"
        assert _estimate_reading_time(0) == "2分钟"

    def test_escape_md_table_cell(self) -> None:
        """表格单元格中的 | 必须转义，否则会拆列。"""
        assert _escape_md_table_cell("a|b") == r"a\|b"
        assert _escape_md_table_cell("a\nb") == "a b"

    def test_get_score_stars(self) -> None:
        """Test star rating based on score."""
        assert _get_score_stars(95) == "⭐⭐⭐⭐⭐"
        assert _get_score_stars(85) == "⭐⭐⭐⭐"
        assert _get_score_stars(75) == "⭐⭐⭐"
        assert _get_score_stars(65) == "⭐⭐"
        assert _get_score_stars(55) == "⭐"


class TestRenderMarkdown:
    """Tests for render_markdown function."""

    def test_render_basic_digest(self) -> None:
        """Test basic digest rendering with no articles."""
        generated_at = datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)

        markdown = render_markdown(
            generated_at=generated_at,
            hours=24,
            fetched_count=15,
            candidate_count=10,
            scored_articles=[],
        )

        # 新格式检查
        assert "📰 Readwise 日报" in markdown
        assert "2024年01月15日" in markdown
        assert "📊 概览" in markdown
        assert "拉取文章 | 15 篇" in markdown
        assert "最终入选 | 0 篇" in markdown
        assert "📝 状态" in markdown
        assert "今天没有找到符合条件的文章" in markdown

    def test_render_with_articles(self) -> None:
        """Test rendering with scored articles."""
        generated_at = datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)

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
            word_count=1500,
            reading_time="6 mins",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            published_date=None,
            summary="Readwise summary",
            image_url=None,
            notes=None,
            reading_progress=0.7,
            tags=["tech", "AI"],
            text_content="Content",
        )

        scored = ScoredArticle(
            article=article,
            overall_score=88,
            relevance_score=90,
            novelty_score=85,
            actionability_score=89,
            summary="Generated summary for the article",
            recommendation="Strongly recommended for tech readers",
            keywords=["AI", "technology", "future"],
        )

        markdown = render_markdown(
            generated_at=generated_at,
            hours=24,
            fetched_count=20,
            candidate_count=15,
            scored_articles=[scored],
        )

        # 新格式检查
        assert "📰 Readwise 日报" in markdown
        assert "⭐ 编辑推荐" in markdown  # 88分 >= 85
        assert "Test Article" in markdown
        assert "Test Author" in markdown
        assert "🚀 快速浏览" in markdown
        assert "📖 精选详情" in markdown
        assert "88" in markdown
        assert "相关性 | 90" in markdown
        assert "关键词：" in markdown
        assert "阅读原文" in markdown
        assert "摘要" in markdown
        assert "入选理由" in markdown

    def test_render_quick_browse_title_with_pipe(self) -> None:
        """标题中的 | 会误解析为表格列分隔符，应转义。"""
        generated_at = datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)
        article = Article(
            id="pipe-001",
            title="Pipe|In|Title",
            url="https://example.com/p",
            source_url=None,
            author="A",
            source="S",
            category=None,
            location=None,
            site_name="Site",
            word_count=300,
            reading_time=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            published_date=None,
            summary="S",
            image_url=None,
            notes=None,
            reading_progress=None,
        )
        scored = ScoredArticle(
            article=article,
            overall_score=70,
            relevance_score=70,
            novelty_score=70,
            actionability_score=70,
            summary="X",
            recommendation="Y",
            keywords=[],
        )
        markdown = render_markdown(
            generated_at=generated_at,
            hours=24,
            fetched_count=1,
            candidate_count=1,
            scored_articles=[scored],
        )
        assert "[Pipe\\|In\\|Title](#1)" in markdown

    def test_render_multiple_articles(self) -> None:
        """Test rendering multiple articles with correct structure."""
        generated_at = datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)

        articles = [
            ScoredArticle(
                article=Article(
                    id=f"test-{i:03d}",
                    title=f"Article {i}",
                    url=f"https://example.com/{i}",
                    source_url=None,
                    author=f"Author {i}",
                    source=None,
                    category=None,
                    location=None,
                    site_name=f"Site {i}",
                    word_count=500 * i,
                    reading_time=None,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    published_date=None,
                    summary=f"Summary {i}",
                    image_url=None,
                    notes=None,
                    reading_progress=None,
                ),
                overall_score=90 - i * 5,  # 85, 80, 75
                relevance_score=85,
                novelty_score=80,
                actionability_score=75,
                summary=f"Summary {i}",
                recommendation=f"Rec {i}",
                keywords=[],
            )
            for i in range(1, 4)
        ]

        markdown = render_markdown(
            generated_at=generated_at,
            hours=24,
            fetched_count=10,
            candidate_count=5,
            scored_articles=articles,
        )

        # 检查快速浏览表格
        assert "🚀 快速浏览" in markdown
        assert "| 1 |" in markdown
        assert "| 2 |" in markdown
        assert "| 3 |" in markdown

        # 检查详情锚点
        assert '<a name="1"></a>' in markdown
        assert '<a name="2"></a>' in markdown
        assert '<a name="3"></a>' in markdown

        # 检查编辑推荐（只有第一篇85分>=85）
        assert "⭐ 编辑推荐" in markdown
        assert "Article 1" in markdown

    def test_render_without_editors_picks(self) -> None:
        """Test rendering when no articles qualify as editor's picks."""
        generated_at = datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)

        articles = [
            ScoredArticle(
                article=Article(
                    id="low-001",
                    title="Low Score Article",
                    url="https://example.com/low",
                    source_url=None,
                    author="Author",
                    source=None,
                    category=None,
                    location=None,
                    site_name="Site",
                    word_count=None,
                    reading_time=None,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    published_date=None,
                    summary="Summary",
                    image_url=None,
                    notes=None,
                    reading_progress=None,
                ),
                overall_score=80,  # < 85, 不应出现在编辑推荐
                relevance_score=80,
                novelty_score=80,
                actionability_score=80,
                summary="Low score summary",
                recommendation="Rec",
                keywords=["tag"],
            )
        ]

        markdown = render_markdown(
            generated_at=generated_at,
            hours=24,
            fetched_count=5,
            candidate_count=3,
            scored_articles=articles,
        )

        # 不应有编辑推荐部分
        assert "⭐ 编辑推荐" not in markdown
        assert "🚀 快速浏览" in markdown


class TestWriteMarkdown:
    """Tests for write_markdown function."""

    def test_write_creates_file(self, tmp_path: Path) -> None:
        """Test markdown file is created correctly."""
        generated_at = datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)
        content = "# Test Digest\n\nContent here"

        output_path = write_markdown(tmp_path, generated_at, content)

        assert output_path.exists()
        assert output_path.name == "AI-digest_20240115_103000.md"
        assert output_path.read_text(encoding="utf-8") == content

    def test_write_creates_directories(self, tmp_path: Path) -> None:
        """Test output directory is created if it doesn't exist."""
        generated_at = datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)
        content = "# Test Digest"
        nested_dir = tmp_path / "nested" / "output"

        output_path = write_markdown(nested_dir, generated_at, content)

        assert nested_dir.exists()
        assert output_path.exists()
