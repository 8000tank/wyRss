from __future__ import annotations

import argparse
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from time import perf_counter
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.clients.llm_client import LLMClient
from src.clients.readwise_client import ReadwiseClient
from src.config import FetchBucket, Settings
from src.models import Article
from src.pipeline.filtering import filter_articles, select_diverse_candidates
from src.pipeline.ranking import score_articles
from src.pipeline.source_taxonomy import publisher_key, topic_for
from src.renderers.markdown_renderer import render_markdown, write_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a Readwise daily digest.")
    parser.add_argument("--hours", type=int, help="Override the digest time window in hours.")
    parser.add_argument("--top-n", type=int, help="Override the number of selected articles.")
    parser.add_argument(
        "--candidate-limit",
        type=int,
        help="Override the maximum number of candidate articles sent to the ranking step.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level.",
    )
    return parser


def _format_topic_distribution(articles: list[Article], allowed_topics: list[str]) -> str:
    counter = Counter(topic_for(a, allowed_topics) for a in articles)
    parts = [f"{topic}={count}" for topic, count in sorted(counter.items())]
    return ", ".join(parts) if parts else "(empty)"


def _format_publisher_distribution(articles: list[Article]) -> str:
    counter = Counter(publisher_key(a) for a in articles)
    return ", ".join(f"{publisher}={count}" for publisher, count in counter.most_common()) or "(empty)"


def _format_fetch_buckets(buckets: list[FetchBucket], default_location: str | None) -> str:
    parts: list[str] = []
    for bucket in buckets:
        category = bucket.category or "all"
        location = bucket.location if bucket.location is not None else default_location
        location_suffix = f"@{location}" if location else ""
        parts.append(f"{category}{location_suffix}:{bucket.max_items}")
    return ", ".join(parts)


def _digest_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        logging.warning("Unknown DIGEST_TIMEZONE=%r; falling back to UTC.", name)
        return ZoneInfo("UTC")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    settings = Settings.from_env()
    hours = args.hours or settings.digest_hours
    top_n = args.top_n or settings.digest_top_n
    candidate_limit = args.candidate_limit or settings.digest_candidate_limit
    pre_score_limit = min(settings.digest_pre_score_limit, candidate_limit)
    updated_after = datetime.now(timezone.utc) - timedelta(hours=hours)
    pipeline_started_at = perf_counter()

    readwise_client = ReadwiseClient(
        token=settings.readwise_token,
        base_url=settings.readwise_base_url,
        timeout_seconds=settings.request_timeout_seconds,
    )
    llm_client = LLMClient(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        extra_body=settings.llm_extra_body(),
    )

    logging.info("Verifying Readwise token.")
    readwise_client.verify_token()

    buckets = settings.effective_buckets()
    logging.info(
        "Fetching documents from Readwise Reader (buckets=%s).",
        _format_fetch_buckets(buckets, settings.readwise_location),
    )
    fetch_started_at = perf_counter()
    if settings.readwise_fetch_buckets:
        articles = readwise_client.list_documents_by_buckets(
            buckets,
            updated_after=updated_after,
            location=settings.readwise_location,
            with_html_content=settings.readwise_with_html_content,
        )
    else:
        # Legacy single-bucket path keeps existing CLI behaviour for users
        # who never set READWISE_FETCH_BUCKETS.
        articles = readwise_client.list_documents(
            updated_after=updated_after,
            location=settings.readwise_location,
            category=settings.readwise_category,
            with_html_content=settings.readwise_with_html_content,
            max_items=candidate_limit,
        )
    fetch_elapsed = perf_counter() - fetch_started_at
    logging.info(
        "Fetched %d article(s) in %.2fs.",
        len(articles),
        fetch_elapsed,
    )
    if articles:
        per_category = Counter((a.category or "?").lower() for a in articles)
        logging.info(
            "  Fetch per-category: %s",
            ", ".join(f"{cat}={count}" for cat, count in sorted(per_category.items())),
        )

    logging.info("Filtering and deduplicating articles.")
    filter_started_at = perf_counter()
    candidates = filter_articles(
        articles,
        hours=hours,
        max_candidates=candidate_limit,
        max_published_age_days=settings.digest_max_published_age_days,
    )
    filter_elapsed = perf_counter() - filter_started_at
    logging.info(
        "Filtering kept %d/%d article(s) in %.2fs.",
        len(candidates),
        len(articles),
        filter_elapsed,
    )

    logging.info("Selecting diverse candidates before LLM scoring.")
    pre_score_started_at = perf_counter()
    pre_scored_candidates = select_diverse_candidates(
        candidates,
        max_candidates=pre_score_limit,
        allowed_topics=settings.digest_topic_buckets,
    )
    pre_score_elapsed = perf_counter() - pre_score_started_at
    logging.info(
        "Pre-score diversity selection kept %d/%d article(s) in %.2fs.",
        len(pre_scored_candidates),
        len(candidates),
        pre_score_elapsed,
    )
    if pre_scored_candidates:
        logging.info(
            "  Pre-score topic distribution: %s",
            _format_topic_distribution(pre_scored_candidates, settings.digest_topic_buckets),
        )

    logging.info("Scoring candidate articles with the configured LLM.")
    scoring_started_at = perf_counter()
    scored_articles = score_articles(
        pre_scored_candidates,
        llm_client=llm_client,
        max_input_chars=settings.llm_max_input_chars,
        digest_language=settings.digest_language,
        scoring_focus=settings.digest_scoring_focus,
        top_n=top_n,
        llm_concurrency=settings.llm_concurrency,
        max_per_site=settings.digest_max_per_site,
        max_per_author=settings.digest_max_per_author,
    )
    scoring_elapsed = perf_counter() - scoring_started_at
    logging.info(
        "Scored %d article(s) in %.2fs using concurrency=%d; selected %d final article(s).",
        len(pre_scored_candidates),
        scoring_elapsed,
        settings.llm_concurrency,
        len(scored_articles),
    )
    if scored_articles:
        final_articles = [item.article for item in scored_articles]
        logging.info(
            "  Final topic distribution: %s",
            _format_topic_distribution(final_articles, settings.digest_topic_buckets),
        )
        logging.info(
            "  Final publisher distribution: %s",
            _format_publisher_distribution(final_articles),
        )

    generated_at = datetime.now(_digest_timezone(settings.digest_timezone))
    render_started_at = perf_counter()
    markdown = render_markdown(
        generated_at=generated_at,
        hours=hours,
        fetched_count=len(articles),
        candidate_count=len(pre_scored_candidates),
        scored_articles=scored_articles,
    )
    output_path = write_markdown(settings.digest_output_dir, generated_at, markdown)
    render_elapsed = perf_counter() - render_started_at
    total_elapsed = perf_counter() - pipeline_started_at

    logging.info("Rendered and wrote digest in %.2fs.", render_elapsed)
    logging.info("Digest generated successfully in %.2fs: %s", total_elapsed, output_path)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
