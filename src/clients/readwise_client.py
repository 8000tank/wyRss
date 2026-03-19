from __future__ import annotations

import re
import time
from datetime import date, datetime
from html import unescape
from html.parser import HTMLParser
from typing import Any

import requests

from src.models import Article


class _HTMLToTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self._parts.append(data.strip())

    def get_text(self) -> str:
        return " ".join(self._parts)


def _html_to_text(html_content: str | None) -> str | None:
    if not html_content:
        return None
    parser = _HTMLToTextParser()
    parser.feed(html_content)
    raw = unescape(parser.get_text())
    return re.sub(r"\s+", " ", raw).strip() or None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


class ReadwiseClient:
    def __init__(self, token: str, base_url: str, timeout_seconds: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Authorization": f"Token {token}",
            }
        )

    def verify_token(self) -> None:
        response = self.session.get(
            "https://readwise.io/api/v2/auth/",
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()

    def _request(self, method: str, endpoint: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        while True:
            response = self.session.request(
                method,
                url,
                params=params,
                timeout=self.timeout_seconds,
            )
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "5"))
                time.sleep(retry_after)
                continue
            response.raise_for_status()
            return response.json()

    def list_documents(
        self,
        *,
        updated_after: datetime | None = None,
        location: str | None = None,
        category: str | None = None,
        with_html_content: bool = True,
        limit_per_page: int = 100,
        max_items: int | None = None,
    ) -> list[Article]:
        params: dict[str, Any] = {
            "limit": max(1, min(limit_per_page, 100)),
            "withHtmlContent": str(with_html_content).lower(),
        }
        if updated_after is not None:
            params["updatedAfter"] = updated_after.isoformat()
        if location:
            params["location"] = location
        if category:
            params["category"] = category

        page_cursor: str | None = None
        articles: list[Article] = []

        while True:
            page_params = dict(params)
            if page_cursor:
                page_params["pageCursor"] = page_cursor

            payload = self._request("GET", "/list/", params=page_params)
            for item in payload.get("results", []):
                articles.append(self._normalize_document(item))
                if max_items is not None and len(articles) >= max_items:
                    return articles

            page_cursor = payload.get("nextPageCursor")
            if not page_cursor:
                return articles

    def _normalize_document(self, item: dict[str, Any]) -> Article:
        raw_tags = item.get("tags") or []
        if isinstance(raw_tags, dict):
            tags = [str(tag).strip() for tag in raw_tags.keys() if str(tag).strip()]
        elif isinstance(raw_tags, list):
            tags = [str(tag).strip() for tag in raw_tags if str(tag).strip()]
        else:
            tags = []

        html_content = item.get("html_content")
        return Article(
            id=str(item["id"]),
            title=(item.get("title") or "").strip() or "(untitled)",
            url=(item.get("url") or "").strip(),
            source_url=(item.get("source_url") or "").strip() or None,
            author=(item.get("author") or "").strip() or None,
            source=(item.get("source") or "").strip() or None,
            category=(item.get("category") or "").strip() or None,
            location=(item.get("location") or "").strip() or None,
            site_name=(item.get("site_name") or "").strip() or None,
            word_count=item.get("word_count"),
            reading_time=(item.get("reading_time") or "").strip() or None,
            created_at=_parse_datetime(item.get("created_at")),
            updated_at=_parse_datetime(item.get("updated_at")),
            published_date=_parse_date(item.get("published_date")),
            summary=(item.get("summary") or "").strip() or None,
            image_url=(item.get("image_url") or "").strip() or None,
            notes=(item.get("notes") or "").strip() or None,
            reading_progress=item.get("reading_progress"),
            tags=tags,
            html_content=html_content,
            text_content=_html_to_text(html_content),
            parent_id=(item.get("parent_id") or "").strip() or None,
        )
