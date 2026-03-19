from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(slots=True)
class Article:
    id: str
    title: str
    url: str
    source_url: str | None
    author: str | None
    source: str | None
    category: str | None
    location: str | None
    site_name: str | None
    word_count: int | None
    reading_time: str | None
    created_at: datetime | None
    updated_at: datetime | None
    published_date: date | None
    summary: str | None
    image_url: str | None
    notes: str | None
    reading_progress: float | None
    tags: list[str] = field(default_factory=list)
    html_content: str | None = None
    text_content: str | None = None
    parent_id: str | None = None

    @property
    def canonical_url(self) -> str:
        return self.source_url or self.url


@dataclass(slots=True)
class ScoredArticle:
    article: Article
    overall_score: int
    relevance_score: int
    novelty_score: int
    actionability_score: int
    summary: str
    recommendation: str
    keywords: list[str] = field(default_factory=list)
    raw_response: str | None = None
