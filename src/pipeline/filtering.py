from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from src.models import Article
from src.pipeline.source_taxonomy import publisher_key, topic_for


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _infer_date_from_title(title: str) -> date | None:
    """Best-effort freshness signal for titles like 26/3/23 or 2026.04.24."""
    matches = re.findall(
        r"(?<!\d)(20\d{2}|2\d)[./-](\d{1,2})[./-](\d{1,2})(?!\d)",
        title,
    )
    parsed: list[date] = []
    for raw_year, raw_month, raw_day in matches:
        year = int(raw_year)
        if year < 100:
            year += 2000
        candidate = _safe_date(year, int(raw_month), int(raw_day))
        if candidate is not None:
            parsed.append(candidate)
    return max(parsed) if parsed else None


def _article_published_signal(article: Article) -> date | None:
    return article.published_date or _infer_date_from_title(article.title)


_EMAIL_NOISE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b\d{4,8}\b.*\b(verification|confirmation|login|security)\s+code\b"),
    re.compile(r"\b(verification|confirmation|login|security)\s+code\b"),
    re.compile(r"\b(confirm|verify)\s+(your\s+)?(email|subscription|account)\b"),
    re.compile(r"\bsubscription\s+confirmed\b"),
    re.compile(r"\byou're\s+subscribed\b"),
    re.compile(r"\bthanks?\s+for\s+(subscribing|signing\s+up)\b"),
)


def _normalize_email_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.replace("’", "'").strip().lower())


def _is_email_noise(article: Article) -> bool:
    """Filter subscription/admin emails while keeping actual newsletter issues."""
    if (article.category or "").strip().lower() != "email":
        return False

    title = _normalize_email_text(article.title)
    publisher = _normalize_email_text(
        " ".join(
            part
            for part in [article.author, article.site_name, article.source]
            if part
        )
    )
    haystack = f"{title} {publisher}".strip()

    if any(pattern.search(haystack) for pattern in _EMAIL_NOISE_PATTERNS):
        return True

    known_onboarding_publishers = (
        "import ai",
        "ben's bites",
        "the code",
        "superhuman",
        "the neuron",
        "substack",
    )
    if title.startswith("welcome to ") and any(
        publisher_name in haystack for publisher_name in known_onboarding_publishers
    ):
        return True
    if title.startswith("you're officially ") and any(
        publisher_name in haystack for publisher_name in known_onboarding_publishers
    ):
        return True
    if "we've got ai treats for you" in title and "the neuron" in haystack:
        return True

    return False


def filter_articles(
    articles: list[Article],
    *,
    hours: int,
    max_candidates: int,
    max_published_age_days: int | None = None,
) -> list[Article]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    published_cutoff = (
        (datetime.now(timezone.utc).date() - timedelta(days=max_published_age_days))
        if max_published_age_days is not None and max_published_age_days >= 0
        else None
    )
    unique: dict[str, Article] = {}

    for article in articles:
        if article.parent_id:
            continue
        if not article.title or not article.canonical_url:
            continue
        if _is_email_noise(article):
            continue
        if article.updated_at and article.updated_at < cutoff:
            continue
        published_signal = _article_published_signal(article)
        if published_cutoff is not None and published_signal is not None:
            if published_signal < published_cutoff:
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
    """Used by select_diverse_candidates. Aggregator-aware via publisher_key."""
    return publisher_key(article)


def _author_key(article: Article) -> str:
    normalized = _normalize_key(article.author)
    return normalized or "unknown-author"


def select_diverse_candidates(
    articles: list[Article],
    *,
    max_candidates: int,
    allowed_topics: list[str] | None = None,
) -> list[Article]:
    """Greedily balance topic, source and author diversity before LLM scoring.

    Priority tuple per remaining article (lower wins):
    ``(topic_count, source_count, author_count, index)``.

    ``allowed_topics`` is forwarded to :func:`topic_for` so the topic bucketing
    matches the rest of the pipeline. When ``None``, the taxonomy module's
    default mapping is used and all inferred topics are accepted.
    """
    if max_candidates <= 0:
        return []

    remaining = sorted(articles, key=_article_sort_timestamp, reverse=True)
    selected: list[Article] = []
    topic_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    author_counts: dict[str, int] = {}

    while remaining and len(selected) < max_candidates:
        best_index = 0
        best_priority: tuple[int, int, int, int] | None = None

        for index, article in enumerate(remaining):
            topic_key = topic_for(article, allowed_topics)
            source_key = _source_key(article)
            author_key = _author_key(article)
            priority = (
                topic_counts.get(topic_key, 0),
                source_counts.get(source_key, 0),
                author_counts.get(author_key, 0),
                index,
            )
            if best_priority is None or priority < best_priority:
                best_priority = priority
                best_index = index

        chosen = remaining.pop(best_index)
        selected.append(chosen)

        topic_key = topic_for(chosen, allowed_topics)
        source_key = _source_key(chosen)
        author_key = _author_key(chosen)
        topic_counts[topic_key] = topic_counts.get(topic_key, 0) + 1
        source_counts[source_key] = source_counts.get(source_key, 0) + 1
        author_counts[author_key] = author_counts.get(author_key, 0) + 1

    return selected
