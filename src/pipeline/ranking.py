from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from src.clients.llm_client import LLMClient
from src.models import Article, ScoredArticle

logger = logging.getLogger(__name__)


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _build_article_payload(article: Article, max_input_chars: int) -> str:
    content = article.text_content or article.summary or ""
    excerpt = _truncate_text(content, max_input_chars)
    return (
        f"标题: {article.title}\n"
        f"来源站点: {article.site_name or '未知'}\n"
        f"作者: {article.author or '未知'}\n"
        f"原文链接: {article.canonical_url}\n"
        f"发布时间: {article.published_date or '未知'}\n"
        f"Readwise摘要: {article.summary or '无'}\n"
        f"正文摘录:\n{excerpt or '无可用正文'}"
    )


def _coerce_keywords(raw_value: Any) -> list[str]:
    if isinstance(raw_value, list):
        return [str(item).strip() for item in raw_value if str(item).strip()]
    return []


def _fallback_scored_article(article: Article) -> ScoredArticle:
    return ScoredArticle(
        article=article,
        overall_score=50,
        relevance_score=50,
        novelty_score=50,
        actionability_score=50,
        summary=article.summary or "LLM 评分失败，暂时使用 Readwise 自带摘要。",
        recommendation="建议人工复核这篇文章是否应当入选日报。",
        keywords=article.tags,
        raw_response=None,
    )


def _score_single_article(
    article: Article,
    *,
    llm_client: LLMClient,
    system_prompt: str,
    max_input_chars: int,
    digest_language: str,
    scoring_focus: str,
) -> ScoredArticle:
    user_prompt = (
        f"输出语言: {digest_language}\n"
        f"排序目标: {scoring_focus}\n"
        "请重点判断这篇文章是否值得进入今天的资讯日报。\n\n"
        f"{_build_article_payload(article, max_input_chars)}"
    )

    try:
        payload = llm_client.chat_json(system_prompt=system_prompt, user_prompt=user_prompt)
        return ScoredArticle(
            article=article,
            overall_score=int(payload["overall_score"]),
            relevance_score=int(payload["relevance_score"]),
            novelty_score=int(payload["novelty_score"]),
            actionability_score=int(payload["actionability_score"]),
            summary=str(payload["summary"]).strip(),
            recommendation=str(payload["recommendation"]).strip(),
            keywords=_coerce_keywords(payload.get("keywords")),
            raw_response=str(payload),
        )
    except Exception as e:
        logger.error(
            "LLM scoring failed for article '%s': %s",
            article.title[:80],
            repr(e),
            exc_info=True,
        )
        return _fallback_scored_article(article)


def score_articles(
    articles: list[Article],
    *,
    llm_client: LLMClient,
    max_input_chars: int,
    digest_language: str,
    scoring_focus: str,
    top_n: int,
    llm_concurrency: int = 1,
) -> list[ScoredArticle]:
    system_prompt = (
        "你是一名严谨的资讯编辑。"
        "请根据文章内容输出一个 JSON 对象，不要输出额外解释。"
        "JSON 必须包含以下字段："
        "overall_score, relevance_score, novelty_score, actionability_score, summary, recommendation, keywords。"
        "其中四个分数字段必须是 0 到 100 的整数，summary 和 recommendation 使用简洁自然语言，"
        "keywords 是字符串数组，最多 5 个。"
    )

    concurrency = max(1, llm_concurrency)
    if concurrency == 1 or len(articles) <= 1:
        results = [
            _score_single_article(
                article,
                llm_client=llm_client,
                system_prompt=system_prompt,
                max_input_chars=max_input_chars,
                digest_language=digest_language,
                scoring_focus=scoring_focus,
            )
            for article in articles
        ]
    else:
        with ThreadPoolExecutor(max_workers=min(concurrency, len(articles))) as executor:
            results = list(
                executor.map(
                    lambda article: _score_single_article(
                        article,
                        llm_client=llm_client,
                        system_prompt=system_prompt,
                        max_input_chars=max_input_chars,
                        digest_language=digest_language,
                        scoring_focus=scoring_focus,
                    ),
                    articles,
                )
            )

    results.sort(
        key=lambda item: (
            item.overall_score,
            item.relevance_score,
            item.novelty_score,
            item.actionability_score,
        ),
        reverse=True,
    )

    # 应用作者多样性限制：同一作者最多入选2篇
    results = _apply_author_diversity(results, max_per_author=2)

    return results[:top_n]


def _apply_author_diversity(
    scored_articles: list[ScoredArticle],
    max_per_author: int = 2,
) -> list[ScoredArticle]:
    """限制同一作者的文章数量，确保来源多样性。"""
    author_count: dict[str, int] = {}
    diversified: list[ScoredArticle] = []

    for article in scored_articles:
        author = article.article.author or "未知作者"
        current_count = author_count.get(author, 0)

        if current_count < max_per_author:
            diversified.append(article)
            author_count[author] = current_count + 1
        # 如果超过限制，跳过这篇文章

    return diversified
