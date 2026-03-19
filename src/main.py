from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta, timezone

from src.clients.llm_client import LLMClient
from src.clients.readwise_client import ReadwiseClient
from src.config import Settings
from src.pipeline.filtering import filter_articles
from src.pipeline.ranking import score_articles
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
    updated_after = datetime.now(timezone.utc) - timedelta(hours=hours)

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
    )

    logging.info("Verifying Readwise token.")
    readwise_client.verify_token()

    logging.info("Fetching documents from Readwise Reader.")
    articles = readwise_client.list_documents(
        updated_after=updated_after,
        location=settings.readwise_location,
        category=settings.readwise_category,
        with_html_content=settings.readwise_with_html_content,
        max_items=candidate_limit,
    )

    logging.info("Filtering and deduplicating articles.")
    candidates = filter_articles(
        articles,
        hours=hours,
        max_candidates=candidate_limit,
    )

    logging.info("Scoring candidate articles with the configured LLM.")
    scored_articles = score_articles(
        candidates,
        llm_client=llm_client,
        max_input_chars=settings.llm_max_input_chars,
        digest_language=settings.digest_language,
        scoring_focus=settings.digest_scoring_focus,
        top_n=top_n,
    )

    generated_at = datetime.now(timezone.utc)
    markdown = render_markdown(
        generated_at=generated_at,
        hours=hours,
        fetched_count=len(articles),
        candidate_count=len(candidates),
        scored_articles=scored_articles,
    )
    output_path = write_markdown(settings.digest_output_dir, generated_at, markdown)

    logging.info("Digest generated successfully: %s", output_path)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
