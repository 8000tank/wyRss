from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
