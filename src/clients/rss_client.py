"""Direct RSS fetching client — replaces Readwise API dependency.

Parses OPML source lists, fetches RSS/Atom feeds, extracts full text
from article URLs, and returns standardised :class:`Article` objects
compatible with the existing scoring pipeline.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from html import unescape
from typing import Any
from urllib.parse import urlparse

import feedparser
import requests
import trafilatura

from src.models import Article

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OPML parsing
# ---------------------------------------------------------------------------

def parse_opml(text: str) -> list[FeedSource]:
    """Parse an OPML file and return a flat list of :class:`FeedSource`.

    Handles nested <outline> elements (categories containing feeds).
    """
    root = ET.fromstring(text)
    sources: list[FeedSource] = []
    _walk_outline(root, sources, category=None)
    return sources


def _walk_outline(
    element: ET.Element,
    sources: list[FeedSource],
    category: str | None,
) -> None:
    """Recursively walk OPML <outline> tree."""
    text = element.get("title") or element.get("text") or ""
    xml_url = element.get("xmlUrl") or element.get("xmlurl") or ""
    html_url = element.get("htmlUrl") or element.get("htmlurl") or ""

    children = list(element)
    if xml_url:
        # This is a feed entry
        feed_type = _infer_feed_type(xml_url)
        sources.append(FeedSource(
            name=text.strip(),
            url=xml_url.strip(),
            home_url=html_url.strip() or None,
            category=category or _guess_category_from_name(text),
            feed_type=feed_type,
        ))
    else:
        # This is a category/folder — recurse into children
        new_category = text.strip() if text.strip() else category
        for child in children:
            _walk_outline(child, sources, category=new_category)


def _infer_feed_type(url: str) -> str:
    """Detect special feed types from URL patterns."""
    url_lower = url.lower()
    if "wechat2rss" in url_lower or "weixin" in url_lower:
        return "wechat"
    if "xiaoyuzhou" in url_lower:
        return "podcast"
    if "youtube.com/feeds" in url_lower:
        return "youtube"
    return "rss"


def _guess_category_from_name(name: str) -> str:
    """Best-effort category from feed name keywords."""
    name_lower = name.lower()
    if any(kw in name_lower for kw in ("ai", "deepseek", "智谱", "openai", "anthropic", "大模型", "机器之心", "新智元", "量子位", "claude", "gpt")):
        return "ai"
    if any(kw in name_lower for kw in ("安全", "security", "威胁", "奇安信", "玄武")):
        return "security"
    if any(kw in name_lower for kw in ("云", "cloud", "k8s", "kubernetes", "容器")):
        return "infra"
    if any(kw in name_lower for kw in ("research", "berkeley", "bair", "arxiv", "论文")):
        return "research"
    if any(kw in name_lower for kw in ("verge", "tech", "科技", "产品", "商业", "创业", "founder")):
        return "business"
    return "other"


# ---------------------------------------------------------------------------
# Feed source dataclass
# ---------------------------------------------------------------------------

class FeedSource:
    """A single RSS/Atom feed to fetch."""
    __slots__ = ("name", "url", "home_url", "category", "feed_type")

    def __init__(
        self,
        name: str,
        url: str,
        home_url: str | None = None,
        category: str = "other",
        feed_type: str = "rss",
    ) -> None:
        self.name = name
        self.url = url
        self.home_url = home_url
        self.category = category
        self.feed_type = feed_type


# ---------------------------------------------------------------------------
# RSS feed fetching + full-text extraction
# ---------------------------------------------------------------------------

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; wyRss/2.0; +https://github.com/readwise-digest)"
)


def fetch_feed_articles(
    source: FeedSource,
    *,
    updated_after: datetime,
    session: requests.Session | None = None,
    timeout_seconds: int = 30,
    fetch_full_text: bool = True,
) -> list[Article]:
    """Fetch articles from a single RSS feed, optionally extracting full text.

    Returns articles published/updated after *updated_after*.
    """
    sess = session or requests.Session()
    headers = {"User-Agent": _DEFAULT_USER_AGENT}

    try:
        resp = sess.get(source.url, headers=headers, timeout=timeout_seconds)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("Failed to fetch feed %r (%s): %s", source.name, source.url, exc)
        return []

    feed = feedparser.parse(resp.content)
    if feed.bozo and not feed.entries:
        logger.warning("Feedparse error for %r: %s", source.name, feed.bozo_exception)
        return []

    articles: list[Article] = []
    for entry in feed.entries:
        article = _entry_to_article(entry, source, updated_after)
        if article is None:
            continue

        # Skip podcasts, videos — no meaningful full text for LLM scoring
        if source.feed_type in ("podcast", "youtube"):
            article.text_content = article.summary or ""
            articles.append(article)
            continue

        # Extract full text: prefer feed's content field, then URL extraction
        if fetch_full_text and article.canonical_url:
            # First try the feed's own content (HTML)
            html_content = None
            if hasattr(entry, 'content') and entry.content:
                html_content = entry.content[0].get('value', '') if entry.content else None

            if html_content and len(html_content.strip()) > 200:
                article.text_content = _clean_html(html_content)
            else:
                # Fall back to URL extraction
                article.text_content = _extract_full_text(
                    article.canonical_url,
                    session=sess,
                    timeout_seconds=timeout_seconds,
                )

            # Fall back to feed summary if all extraction failed
            if not article.text_content:
                article.text_content = _clean_html(article.summary or "")
            # Estimate word count from extracted text
            if article.text_content:
                cjk_chars = len(re.findall(r'[\u4e00-\u9fff]', article.text_content))
                en_words = len(re.findall(r'[a-zA-Z]+', article.text_content))
                article.word_count = cjk_chars + en_words
        else:
            article.text_content = _clean_html(article.summary or "")

        articles.append(article)

    logger.debug(
        "Feed %r: fetched %d entries, %d after cutoff",
        source.name, len(feed.entries), len(articles),
    )
    return articles


def _entry_to_article(
    entry: feedparser.FeedParserDict,
    source: FeedSource,
    cutoff: datetime,
) -> Article | None:
    """Convert a feedparser entry to an Article, or None if too old."""
    # Determine the article link
    link = entry.get("link") or ""
    if not link:
        return None

    # Determine publish/update time using feedparser's pre-parsed struct_time
    published = _parse_feed_time(entry)
    if published and published < cutoff:
        return None

    # Generate stable ID from URL hash (replaces Readwise document ID)
    article_id = hashlib.sha256(link.encode()).hexdigest()[:16]

    title = _clean_html(entry.get("title") or "").strip()
    if not title:
        title = "(untitled)"

    author = entry.get("author") or ""
    summary = entry.get("summary") or entry.get("description") or ""

    # WeChat articles: author is in <dc:creator> or feed title
    if source.feed_type == "wechat" and not author:
        author = source.name

    return Article(
        id=article_id,
        title=title,
        url=link,
        source_url=link,
        author=author.strip() or None,
        source=source.name,
        category="rss",
        location=None,
        site_name=source.name,
        word_count=None,
        reading_time=None,
        created_at=published,
        updated_at=published,
        published_date=published.date() if published else None,
        summary=_clean_html(summary) or None,
        image_url=entry.get("media_thumbnail", [{}])[0].get("url") if entry.get("media_thumbnail") else None,
        notes=None,
        reading_progress=None,
        tags=_extract_tags(entry),
        html_content=None,
        text_content=None,
        parent_id=None,
    )


def _parse_feed_time(entry: feedparser.FeedParserDict) -> datetime | None:
    """Parse publish/update time from a feedparser entry using its pre-parsed struct_time."""
    import calendar

    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            ts = calendar.timegm(parsed)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    return None


def _extract_tags(entry: feedparser.FeedParserDict) -> list[str]:
    """Extract tags/categories from a feed entry."""
    tags = []
    for tag in entry.get("tags", []):
        term = tag.get("term", "").strip()
        if term:
            tags.append(term)
    return tags


def _clean_html(html_str: str) -> str:
    """Strip HTML tags and normalise whitespace."""
    if not html_str:
        return ""
    text = re.sub(r"<[^>]+>", " ", html_str)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_full_text(
    url: str,
    session: requests.Session | None = None,
    timeout_seconds: int = 30,
) -> str | None:
    """Extract readable article text from a URL using trafilatura."""
    sess = session or requests.Session()
    try:
        downloaded = trafilatura.fetch_url(
            url,
            timeout=timeout_seconds,
            session=sess,
        )
        if not downloaded:
            return None
        text = trafilatura.extract(
            downloaded,
            include_formatting=False,
            include_links=False,
            include_tables=False,
            favor_recall=True,
        )
        return text.strip() if text else None
    except Exception as exc:
        logger.debug("Full-text extraction failed for %s: %s", url, exc)
        return None


# ---------------------------------------------------------------------------
# Batch fetch from multiple feeds
# ---------------------------------------------------------------------------

def fetch_all_feeds(
    sources: list[FeedSource],
    *,
    updated_after: datetime,
    timeout_seconds: int = 30,
    fetch_full_text: bool = True,
    per_feed_delay: float = 0.5,
) -> list[Article]:
    """Fetch articles from all configured feeds.

    Returns a flat list, deduplicated by article URL (later occurrence wins
    if the same article appears in multiple feeds).
    """
    session = requests.Session()
    session.headers.update({"User-Agent": _DEFAULT_USER_AGENT})

    all_articles: dict[str, Article] = {}
    for source in sources:
        articles = fetch_feed_articles(
            source,
            updated_after=updated_after,
            session=session,
            timeout_seconds=timeout_seconds,
            fetch_full_text=fetch_full_text,
        )
        for article in articles:
            key = article.canonical_url.strip().lower()
            # Keep the one with richer content
            existing = all_articles.get(key)
            if existing is None or (article.text_content and not existing.text_content):
                all_articles[key] = article
        if per_feed_delay > 0 and source != sources[-1]:
            time.sleep(per_feed_delay)

    return list(all_articles.values())
