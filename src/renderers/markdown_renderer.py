from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.models import ScoredArticle


def _estimate_reading_time(word_count: int | None) -> str:
    """估算阅读时间（按每分钟300字计算）。"""
    if not word_count or word_count <= 0:
        return "2分钟"
    minutes = max(1, word_count // 300)
    return f"{minutes}分钟"


def _escape_md_table_cell(text: str) -> str:
    """转义会破坏 GFM 管道表格的字符（标题中常含 `|`）。"""
    return text.replace("\n", " ").replace("|", "\\|")


def _get_score_stars(score: int) -> str:
    """根据评分返回星级标记。"""
    if score >= 90:
        return "⭐⭐⭐⭐⭐"
    elif score >= 80:
        return "⭐⭐⭐⭐"
    elif score >= 70:
        return "⭐⭐⭐"
    elif score >= 60:
        return "⭐⭐"
    else:
        return "⭐"


def render_markdown(
    *,
    generated_at: datetime,
    hours: int,
    fetched_count: int,
    candidate_count: int,
    scored_articles: list[ScoredArticle],
) -> str:
    if not scored_articles:
        return _render_empty_digest(generated_at, hours, fetched_count, candidate_count)

    lines: list[str] = [
        f"# 📰 AI 日报 - {generated_at.strftime('%Y年%m月%d日')}",
        "",
        "## 📊 概览",
        "",
        f"| 指标 | 数值 |",
        f"|------|------|",
        f"| 生成时间 | {generated_at.strftime('%H:%M')} |",
        f"| 统计窗口 | 最近 {hours} 小时 |",
        f"| 拉取文章 | {fetched_count} 篇 |",
        f"| 候选池 | {candidate_count} 篇 |",
        f"| 最终入选 | {len(scored_articles)} 篇 |",
        "",
    ]

    # 编辑推荐（总分≥85的文章）
    editors_picks = [item for item in scored_articles if item.overall_score >= 85]
    if editors_picks:
        lines.extend([
            "## ⭐ 编辑推荐",
            "",
        ])
        for item in editors_picks[:3]:  # 最多显示3篇
            article = item.article
            lines.append(
                f"- **{article.title}** ({item.overall_score}分) - "
                f"{article.author or '未知作者'}"
            )
        lines.append("")

    # 快速浏览表格
    lines.extend([
        "## 🚀 快速浏览",
        "",
        "| 排名 | 标题 | 评分 | 阅读时间 |",
        "|:----:|------|:----:|---------|",
    ])
    for index, item in enumerate(scored_articles, start=1):
        article = item.article
        title_short = article.title[:30] + "..." if len(article.title) > 30 else article.title
        title_cell = _escape_md_table_cell(title_short)
        reading_time = _estimate_reading_time(article.word_count)
        score_stars = _get_score_stars(item.overall_score)
        lines.append(
            f"| {index} | [{title_cell}](#{index}) | {score_stars} {item.overall_score} | {reading_time} |"
        )
    lines.append("")

    # 精选条目详情
    lines.extend([
        "## 📖 精选详情",
        "",
    ])

    for index, item in enumerate(scored_articles, start=1):
        article = item.article
        reading_time = _estimate_reading_time(article.word_count)

        # 文章标题和锚点
        lines.extend([
            f"### <a name=\"{index}\"></a> {index}. {article.title}",
            "",
            f"**作者：** {article.author or '未知'} ｜ **来源：** {article.site_name or article.source or '未知'} ｜ **阅读时间：** {reading_time}",
            "",
        ])

        # 评分卡片
        lines.extend([
            "| 维度 | 评分 | 说明 |",
            "|------|:----:|------|",
            f"| 总分 | **{item.overall_score}** | {_get_score_stars(item.overall_score)} |",
            f"| 相关性 | {item.relevance_score} | 与AI/技术主题相关度 |",
            f"| 新颖度 | {item.novelty_score} | 信息独特性和时效性 |",
            f"| 可执行性 | {item.actionability_score} | 读者可操作程度 |",
            "",
        ])

        # 关键词标签
        if item.keywords:
            tags = " ".join([f"`{kw}`" for kw in item.keywords[:5]])
            lines.append(f"**关键词：** {tags}")
            lines.append("")

        # 原文链接
        lines.extend([
            f"🔗 [阅读原文]({article.canonical_url})",
            "",
        ])

        # 摘要
        lines.extend([
            "> **摘要**",
            ">",
        ])
        # 摘要分行显示，每行前面加引用标记
        for para in item.summary.split("\n"):
            if para.strip():
                lines.append(f"> {para}")
        lines.append("")

        # 入选理由
        lines.extend([
            "💡 **入选理由**",
            "",
            item.recommendation,
            "",
            "---",
            "",
        ])

    return "\n".join(lines)


def _render_empty_digest(
    generated_at: datetime,
    hours: int,
    fetched_count: int,
    candidate_count: int,
) -> str:
    """渲染空日报（无文章时）。"""
    return (
        f"# 📰 AI 日报 - {generated_at.strftime('%Y年%m月%d日')}\n\n"
        f"## 📊 概览\n\n"
        f"| 指标 | 数值 |\n"
        f"|------|------|\n"
        f"| 生成时间 | {generated_at.strftime('%H:%M')} |\n"
        f"| 统计窗口 | 最近 {hours} 小时 |\n"
        f"| 拉取文章 | {fetched_count} 篇 |\n"
        f"| 候选池 | {candidate_count} 篇 |\n"
        f"| 最终入选 | 0 篇 |\n\n"
        f"## 📝 状态\n\n"
        f"今天没有找到符合条件的文章。\n\n"
        f"**可能原因：**\n"
        f"- RSS 源最近 {hours} 小时没有新文章\n"
        f"- 文章未通过筛选条件\n"
        f"- 所有文章都被过滤或去重\n\n"
        f"**建议：**\n"
        f"- 检查 feeds.txt 中的 RSS 源是否有新内容\n"
        f"- 考虑扩大时间窗口（`DIGEST_HOURS`）\n"
        f"- 调整筛选条件（`DIGEST_TOPIC_BUCKETS`）\n"
    )


def write_markdown(output_dir: Path, generated_at: datetime, content: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / f"AI-digest_{generated_at.strftime('%Y%m%d_%H%M%S')}.md"
    file_path.write_text(content, encoding="utf-8")
    return file_path
