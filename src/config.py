from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class FeedSource:
    """A single RSS/Atom feed to fetch."""
    name: str
    url: str
    category: str = "other"
    feed_type: str = "rss"


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value.strip())


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return float(value.strip())


def _env_str_non_empty(*names: str) -> str:
    """First non-empty stripped value among given env var names."""
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return ""


_DEFAULT_TOPIC_BUCKETS: list[str] = ["ai", "security", "infra", "research", "business", "other"]


def _default_reasoning_split(base_url: str, model: str) -> bool:
    base_url_lower = base_url.lower()
    model_lower = model.lower()
    is_minimax_official_api = (
        "minimaxi.com" in base_url_lower
        or "minimax.io" in base_url_lower
    )
    return is_minimax_official_api and model_lower.startswith(("minimax-m2", "minimax-m3"))


def _parse_feed_list(path: Path) -> list[FeedSource]:
    """Parse a simple feeds.txt file.

    Format: ``name|url|category|feed_type`` (one per line).
    Fields after ``url`` are optional and default to ``other`` / ``rss``.
    Lines starting with ``#`` and blank lines are ignored.
    """
    if not path.is_file():
        logger.warning("Feed list file not found: %s", path)
        return []

    sources: list[FeedSource] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2:
            continue
        name = parts[0]
        url = parts[1]
        category = parts[2] if len(parts) > 2 else "other"
        feed_type = parts[3] if len(parts) > 3 else "rss"
        if name and url:
            sources.append(FeedSource(name=name, url=url, category=category, feed_type=feed_type))
    return sources


def _parse_topic_list(raw: str | None, default: list[str]) -> list[str]:
    if raw is None:
        return list(default)
    text = raw.strip()
    if not text:
        return list(default)
    items = [chunk.strip().lower() for chunk in text.split(",") if chunk.strip()]
    return items or list(default)


@dataclass(slots=True)
class Settings:
    # --- Feed sources ---
    feed_list_path: Path
    feed_opml_path: Path | None
    feed_fetch_full_text: bool
    feed_timeout_seconds: int
    feed_per_feed_delay: float

    # --- Digest ---
    digest_hours: int
    digest_candidate_limit: int
    digest_pre_score_limit: int
    digest_top_n: int
    digest_max_per_site: int
    digest_max_per_author: int
    digest_min_overall_score: int
    digest_topic_buckets: list[str]
    digest_max_published_age_days: int
    digest_timezone: str
    digest_output_dir: Path
    digest_language: str
    digest_scoring_focus: str

    # --- LLM ---
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_timeout_seconds: int
    llm_concurrency: int
    llm_temperature: float
    llm_max_tokens: int
    llm_max_input_chars: int
    llm_reasoning_split: bool

    # --- HTTP ---
    request_timeout_seconds: int

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()

        llm_api_key = _env_str_non_empty("RSS_LLM_API_KEY", "LLM_API_KEY")
        llm_model = _env_str_non_empty("RSS_LLM_MODEL", "LLM_MODEL")
        llm_base_url = (
            _env_str_non_empty("RSS_LLM_BASE_URL", "LLM_BASE_URL")
            or "https://api.openai.com/v1"
        ).rstrip("/")

        missing = [
            name
            for name, value in {
                "RSS_LLM_API_KEY": llm_api_key,
                "RSS_LLM_MODEL": llm_model,
            }.items()
            if not value
        ]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Missing required environment variables: {joined}")

        project_dir = Path(__file__).resolve().parent.parent

        return cls(
            # Feed sources
            feed_list_path=Path(os.getenv("FEED_LIST_PATH", str(project_dir / "feeds.txt"))),
            feed_opml_path=(
                Path(os.getenv("FEED_OPML_PATH")) if os.getenv("FEED_OPML_PATH") else None
            ),
            feed_fetch_full_text=_get_bool("FEED_FETCH_FULL_TEXT", True),
            feed_timeout_seconds=_get_int("FEED_TIMEOUT_SECONDS", 30),
            feed_per_feed_delay=_get_float("FEED_PER_FEED_DELAY", 0.5),

            # Digest
            digest_hours=_get_int("DIGEST_HOURS", 24),
            digest_candidate_limit=_get_int("DIGEST_CANDIDATE_LIMIT", 120),
            digest_pre_score_limit=_get_int("DIGEST_PRE_SCORE_LIMIT", 30),
            digest_top_n=_get_int("DIGEST_TOP_N", 12),
            digest_max_per_site=_get_int("DIGEST_MAX_PER_SITE", 2),
            digest_max_per_author=_get_int("DIGEST_MAX_PER_AUTHOR", 2),
            digest_min_overall_score=_get_int("DIGEST_MIN_OVERALL_SCORE", 50),
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
                "信息价值优先；兼顾 AI 研究/产品、基础设施与云、网络安全、工程实践与行业战略；优先选择有独立观察、数据或可操作结论的内容，避免新闻搬运与公关稿。",
            ).strip(),

            # LLM
            llm_api_key=llm_api_key,
            llm_base_url=llm_base_url,
            llm_model=llm_model,
            llm_timeout_seconds=_get_int("LLM_TIMEOUT_SECONDS", 120),
            llm_concurrency=_get_int("LLM_CONCURRENCY", 2),
            llm_temperature=_get_float("LLM_TEMPERATURE", 0.2),
            llm_max_tokens=_get_int("LLM_MAX_TOKENS", 8192),
            llm_max_input_chars=_get_int("LLM_MAX_INPUT_CHARS", 6000),
            llm_reasoning_split=_get_bool(
                "LLM_REASONING_SPLIT",
                _default_reasoning_split(llm_base_url, llm_model),
            ),

            # HTTP
            request_timeout_seconds=_get_int("REQUEST_TIMEOUT_SECONDS", 30),
        )

    def load_feed_sources(self) -> list[FeedSource]:
        """Load feed sources from feeds.txt and/or OPML file."""
        sources: list[FeedSource] = []

        # Load from feeds.txt
        txt_sources = _parse_feed_list(self.feed_list_path)
        sources.extend(txt_sources)
        if txt_sources:
            logger.info("Loaded %d feed(s) from %s", len(txt_sources), self.feed_list_path)

        # Optionally merge from OPML
        if self.feed_opml_path and self.feed_opml_path.is_file():
            from src.clients.rss_client import parse_opml

            opml_text = self.feed_opml_path.read_text(encoding="utf-8")
            opml_sources = parse_opml(opml_text)
            # Deduplicate by URL
            existing_urls = {s.url.lower() for s in sources}
            new_sources = [
                FeedSource(
                    name=s.name,
                    url=s.url,
                    category=s.category,
                    feed_type=s.feed_type,
                )
                for s in opml_sources
                if s.url.lower() not in existing_urls
            ]
            sources.extend(new_sources)
            if new_sources:
                logger.info("Merged %d feed(s) from OPML %s", len(new_sources), self.feed_opml_path)

        return sources

    def llm_extra_body(self) -> dict[str, object]:
        """Provider-specific OpenAI-compatible request options."""
        if self.llm_reasoning_split:
            return {"reasoning_split": True}
        return {}
