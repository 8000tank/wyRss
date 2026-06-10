from __future__ import annotations

import argparse
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from time import perf_counter
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.clients.llm_client import LLMClient
from src.clients.rss_client import fetch_all_feeds, FeedSource
from src.config import Settings
from src.models import Article
from src.pipeline.filtering import filter_articles, select_diverse_candidates
from src.pipeline.ranking import score_articles
from src.pipeline.source_taxonomy import publisher_key, topic_for
from src.renderers.markdown_renderer import render_markdown, write_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate AI daily digest from RSS feeds.")
    parser.add_argument("--hours", type=int, help="Override the digest time window in hours.")
    parser.add_argument("--top-n", type=int, help="Override the number of selected articles.")
    parser.add_argument(
        "--candidate-limit",
        type=int,
        help="Override the maximum number of candidate articles sent to the ranking step.",
    )
    parser.add_argument(
        "--no-full-text",
        action="store_true",
        help="Skip full-text extraction (use feed summaries only).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch feeds but skip LLM scoring; print candidate summary.",
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
    fetch_full_text = settings.feed_fetch_full_text and not args.no_full_text
    updated_after = datetime.now(timezone.utc) - timedelta(hours=hours)
    pipeline_started_at = perf_counter()

    # Load feed sources
    sources = settings.load_feed_sources()
    if not sources:
        logging.error("No feed sources configured. Check FEED_LIST_PATH or FEED_OPML_PATH.")
        return 1
    logging.info("Loaded %d feed source(s).", len(sources))

    llm_client = LLMClient(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        extra_body=settings.llm_extra_body(),
    )

    # Fetch all feeds
    logging.info("Fetching RSS feeds (full_text=%s, window=%dh)...", fetch_full_text, hours)
    fetch_started_at = perf_counter()
    articles = fetch_all_feeds(
        sources,
        updated_after=updated_after,
        timeout_seconds=settings.feed_timeout_seconds,
        fetch_full_text=fetch_full_text,
        per_feed_delay=settings.feed_per_feed_delay,
    )
    fetch_elapsed = perf_counter() - fetch_started_at
    logging.info(
        "Fetched %d article(s) from %d feed(s) in %.2fs.",
        len(articles),
        len(sources),
        fetch_elapsed,
    )

    if args.dry_run:
        _print_dry_run_summary(articles, hours, sources, settings)
        return 0

    # Filter and deduplicate
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

    # Pre-score diversity selection
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

    # LLM scoring
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

    # Render
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


def _print_dry_run_summary(
    articles: list[Article],
    hours: int,
    sources: list[FeedSource],
    settings: Settings,
) -> None:
    """Print a summary of fetched articles without running LLM scoring."""
    print(f"\n{'='*60}")
    print(f"DRY RUN — Fetched {len(articles)} article(s) from {len(sources)} feed(s)")
    print(f"Time window: {hours}h")
    print(f"{'='*60}")

    if not articles:
        print("(no articles found)")
        return

    for i, article in enumerate(articles, 1):
        topic = topic_for(article, settings.digest_topic_buckets)
        text_len = len(article.text_content or "")
        print(
            f"  {i:3d}. [{topic:8s}] {article.title[:60]}"
            + (f" ({text_len} chars)" if text_len else "")
        )

    print()
    print(f"Topic distribution: {_format_topic_distribution(articles, settings.digest_topic_buckets)}")
    print(f"Publisher distribution: {_format_publisher_distribution(articles)}")


if __name__ == "__main__":
    raise SystemExit(main())
