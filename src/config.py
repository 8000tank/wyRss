from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class FetchBucket:
    category: str | None
    max_items: int
    location: str | None = None


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value)


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return float(value)


def _env_str_non_empty(*names: str) -> str:
    """First non-empty stripped value among given env var names."""
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return ""


def _parse_buckets(raw: str | None) -> list[FetchBucket]:
    """Parse a "category[@location]:max_items,..." spec.

    Returns an empty list on empty/None input or when nothing parses cleanly,
    so callers can fall back to legacy single-bucket behaviour.

    Rules:
    - Each comma-separated entry must be ``category:integer`` or
      ``category@location:integer``; whitespace is stripped.
    - ``category`` may be empty (-> None, meaning "all categories").
    - ``location`` may be omitted (-> caller's global READWISE_LOCATION).
    - Non-positive max_items are skipped.
    - Duplicate category/location pairs: later entry wins.
    - Malformed entries are skipped with a logged warning.
    """
    if raw is None:
        return []
    text = raw.strip()
    if not text:
        return []

    parsed: dict[tuple[str | None, str | None], int] = {}
    order: list[tuple[str | None, str | None]] = []
    for chunk in text.split(","):
        token = chunk.strip()
        if not token:
            continue
        if ":" not in token:
            logger.warning("Ignoring fetch bucket entry without ':' -> %r", token)
            continue
        bucket_part, _, max_part = token.partition(":")
        if "@" in bucket_part:
            category_part, _, location_part = bucket_part.partition("@")
            location = location_part.strip() or None
        else:
            category_part = bucket_part
            location = None
        category = category_part.strip() or None
        try:
            max_items = int(max_part.strip())
        except ValueError:
            logger.warning("Ignoring fetch bucket entry with non-int max -> %r", token)
            continue
        if max_items <= 0:
            logger.warning("Ignoring fetch bucket entry with non-positive max -> %r", token)
            continue
        key = (category, location)
        if key not in parsed:
            order.append(key)
        parsed[key] = max_items

    return [
        FetchBucket(category=category, location=location, max_items=parsed[(category, location)])
        for category, location in order
    ]


def _parse_topic_list(raw: str | None, default: list[str]) -> list[str]:
    if raw is None:
        return list(default)
    text = raw.strip()
    if not text:
        return list(default)
    items = [chunk.strip().lower() for chunk in text.split(",") if chunk.strip()]
    return items or list(default)


_DEFAULT_TOPIC_BUCKETS: list[str] = ["ai", "security", "infra", "research", "business", "other"]


def _default_reasoning_split(base_url: str, model: str) -> bool:
    return "minimaxi.com" in base_url.lower() and model.lower().startswith("minimax-m2")


@dataclass(slots=True)
class Settings:
    readwise_token: str
    readwise_base_url: str
    readwise_location: str | None
    readwise_category: str | None
    readwise_fetch_buckets: list[FetchBucket]
    readwise_with_html_content: bool
    request_timeout_seconds: int
    digest_hours: int
    digest_candidate_limit: int
    digest_pre_score_limit: int
    digest_top_n: int
    digest_max_per_site: int
    digest_max_per_author: int
    digest_topic_buckets: list[str]
    digest_max_published_age_days: int
    digest_timezone: str
    digest_output_dir: Path
    digest_language: str
    digest_scoring_focus: str
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_timeout_seconds: int
    llm_concurrency: int
    llm_temperature: float
    llm_max_tokens: int
    llm_max_input_chars: int
    llm_reasoning_split: bool

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()

        readwise_token = os.getenv("READWISE_TOKEN", "").strip()
        llm_api_key = _env_str_non_empty("RSS_LLM_API_KEY", "LLM_API_KEY")
        llm_model = _env_str_non_empty("RSS_LLM_MODEL", "LLM_MODEL")
        llm_base_url = (
            _env_str_non_empty("RSS_LLM_BASE_URL", "LLM_BASE_URL")
            or "https://api.openai.com/v1"
        ).rstrip("/")

        missing = [
            name
            for name, value in {
                "READWISE_TOKEN": readwise_token,
                "RSS_LLM_API_KEY": llm_api_key,
                "RSS_LLM_MODEL": llm_model,
            }.items()
            if not value
        ]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Missing required environment variables: {joined}")

        readwise_category_raw = os.getenv("READWISE_CATEGORY", "rss")
        readwise_category = readwise_category_raw.strip() or None

        return cls(
            readwise_token=readwise_token,
            readwise_base_url=os.getenv("READWISE_BASE_URL", "https://readwise.io/api/v3").rstrip("/"),
            readwise_location=os.getenv("READWISE_LOCATION", "feed").strip() or None,
            readwise_category=readwise_category,
            readwise_fetch_buckets=_parse_buckets(os.getenv("READWISE_FETCH_BUCKETS")),
            readwise_with_html_content=_get_bool("READWISE_WITH_HTML_CONTENT", True),
            request_timeout_seconds=_get_int("REQUEST_TIMEOUT_SECONDS", 30),
            digest_hours=_get_int("DIGEST_HOURS", 24),
            digest_candidate_limit=_get_int("DIGEST_CANDIDATE_LIMIT", 30),
            digest_pre_score_limit=_get_int("DIGEST_PRE_SCORE_LIMIT", 20),
            digest_top_n=_get_int("DIGEST_TOP_N", 10),
            digest_max_per_site=_get_int("DIGEST_MAX_PER_SITE", 2),
            digest_max_per_author=_get_int("DIGEST_MAX_PER_AUTHOR", 2),
            digest_topic_buckets=_parse_topic_list(
                os.getenv("DIGEST_TOPIC_BUCKETS"),
                _DEFAULT_TOPIC_BUCKETS,
            ),
            digest_max_published_age_days=_get_int("DIGEST_MAX_PUBLISHED_AGE_DAYS", 7),
            digest_timezone=os.getenv("DIGEST_TIMEZONE", "Asia/Shanghai").strip() or "Asia/Shanghai",
            digest_output_dir=Path(os.getenv("DIGEST_OUTPUT_DIR", "output")),
            digest_language=os.getenv("DIGEST_LANGUAGE", "中文").strip() or "中文",
            digest_scoring_focus=os.getenv(
                "DIGEST_SCORING_FOCUS",
                "信息价值优先，其次考虑新颖度、可执行性和与技术/AI资讯的相关性。",
            ).strip(),
            llm_api_key=llm_api_key,
            llm_base_url=llm_base_url,
            llm_model=llm_model,
            llm_timeout_seconds=_get_int("LLM_TIMEOUT_SECONDS", 60),
            llm_concurrency=_get_int("LLM_CONCURRENCY", 1),
            llm_temperature=_get_float("LLM_TEMPERATURE", 0.2),
            llm_max_tokens=_get_int("LLM_MAX_TOKENS", 4096),
            llm_max_input_chars=_get_int("LLM_MAX_INPUT_CHARS", 6000),
            llm_reasoning_split=_get_bool(
                "LLM_REASONING_SPLIT",
                _default_reasoning_split(llm_base_url, llm_model),
            ),
        )

    def effective_buckets(self) -> list[FetchBucket]:
        """Buckets used for fetching. Falls back to legacy single bucket when not set."""
        if self.readwise_fetch_buckets:
            return list(self.readwise_fetch_buckets)
        return [FetchBucket(category=self.readwise_category, max_items=self.digest_candidate_limit)]

    def llm_extra_body(self) -> dict[str, object]:
        """Provider-specific OpenAI-compatible request options."""
        if self.llm_reasoning_split:
            return {"reasoning_split": True}
        return {}
