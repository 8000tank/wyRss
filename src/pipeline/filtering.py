from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from src.models import Article


def filter_articles(
    articles: list[Article],
    *,
    hours: int,
    max_candidates: int,
) -> list[Article]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    unique: dict[str, Article] = {}

    for article in articles:
        if article.parent_id:
            continue
        if not article.title or not article.canonical_url:
            continue
        if article.updated_at and article.updated_at < cutoff:
            continue

        dedupe_key = article.canonical_url.strip().lower()
        existing = unique.get(dedupe_key)
        if existing is None:
            unique[dedupe_key] = article
            continue

        current_updated = article.updated_at or datetime.min.replace(tzinfo=timezone.utc)
        existing_updated = existing.updated_at or datetime.min.replace(tzinfo=timezone.utc)
        if current_updated > existing_updated:
            unique[dedupe_key] = article

    ranked = sorted(
        unique.values(),
        key=lambda item: item.updated_at or item.created_at or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return ranked[:max_candidates]


def _article_sort_timestamp(article: Article) -> datetime:
    return article.updated_at or article.created_at or datetime.min.replace(tzinfo=timezone.utc)


def _normalize_key(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    return normalized or None


def _source_key(article: Article) -> str:
    for value in (article.site_name, article.source):
        normalized = _normalize_key(value)
        if normalized:
            return normalized

    hostname = urlparse(article.canonical_url).netloc.strip().lower()
    return hostname or "unknown-source"


def _author_key(article: Article) -> str:
    normalized = _normalize_key(article.author)
    return normalized or "unknown-author"


def select_diverse_candidates(
    articles: list[Article],
    *,
    max_candidates: int,
) -> list[Article]:
    """Greedily balance source and author diversity before LLM scoring."""
    if max_candidates <= 0:
        return []

    remaining = sorted(articles, key=_article_sort_timestamp, reverse=True)
    selected: list[Article] = []
    source_counts: dict[str, int] = {}
    author_counts: dict[str, int] = {}

    while remaining and len(selected) < max_candidates:
        best_index = 0
        best_priority: tuple[int, int, int] | None = None

        for index, article in enumerate(remaining):
            source_key = _source_key(article)
            author_key = _author_key(article)
            priority = (
                source_counts.get(source_key, 0),
                author_counts.get(author_key, 0),
                index,
            )
            if best_priority is None or priority < best_priority:
                best_priority = priority
                best_index = index

        chosen = remaining.pop(best_index)
        selected.append(chosen)

        source_key = _source_key(chosen)
        author_key = _author_key(chosen)
        source_counts[source_key] = source_counts.get(source_key, 0) + 1
        author_counts[author_key] = author_counts.get(author_key, 0) + 1

    return selected
