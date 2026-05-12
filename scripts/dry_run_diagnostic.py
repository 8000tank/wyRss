"""Dry-run diagnostic for the balanced multi-source pipeline.

Goal: minimise human verification. Calls the **real** Readwise Reader API to
fetch articles, runs the full filter / pre-score diversity / score / final
diversity pipeline using a **deterministic fake LLM** (no token cost), and
prints three distribution tables plus six pass/fail checks.

Usage:
    uv run python scripts/dry_run_diagnostic.py
    uv run python scripts/dry_run_diagnostic.py --hours 48

Exit code 0 if all six checks pass, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

# Allow `uv run python scripts/dry_run_diagnostic.py` from project root.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.clients.readwise_client import ReadwiseClient  # noqa: E402
from src.config import Settings  # noqa: E402
from src.models import Article  # noqa: E402
from src.pipeline.filtering import filter_articles, select_diverse_candidates  # noqa: E402
from src.pipeline.ranking import score_articles  # noqa: E402
from src.pipeline.source_taxonomy import content_type_for, publisher_key, topic_for  # noqa: E402

# ---------------------------------------------------------------------------
# Tiny formatting helpers
# ---------------------------------------------------------------------------


def _hr(title: str = "") -> None:
    if title:
        print(f"\n{'=' * 8} {title} {'=' * (70 - len(title))}")
    else:
        print("=" * 80)


def _print_distribution(label: str, counter: Counter[str], top: int = 10) -> None:
    items = counter.most_common(top)
    if not items:
        print(f"  {label}: (empty)")
        return
    width = max(len(str(name)) for name, _ in items)
    total = sum(counter.values())
    print(f"  {label} (top {min(top, len(items))} of {len(counter)}, total {total}):")
    for name, count in items:
        pct = count / total * 100 if total else 0.0
        print(f"    {str(name).ljust(width)}  {count:>3}  ({pct:5.1f}%)")


def _topic_dist(articles: Iterable[Article], allowed: list[str]) -> Counter[str]:
    return Counter(topic_for(a, allowed) for a in articles)


def _site_dist(articles: Iterable[Article]) -> Counter[str]:
    return Counter((a.site_name or "?") for a in articles)


def _publisher_dist(articles: Iterable[Article]) -> Counter[str]:
    """Diversity-correct 'who published this' distribution (aggregator-aware)."""
    return Counter(publisher_key(a) for a in articles)


def _author_dist(articles: Iterable[Article]) -> Counter[str]:
    return Counter((a.author or "?") for a in articles)


def _category_dist(articles: Iterable[Article]) -> Counter[str]:
    return Counter((a.category or "?").lower() for a in articles)


def _content_type_dist(articles: Iterable[Article]) -> Counter[str]:
    return Counter(content_type_for(a) for a in articles)


# ---------------------------------------------------------------------------
# Deterministic fake LLM
# ---------------------------------------------------------------------------


class _FakeLLM:
    """Returns identical 80/80/80/80 scores so ordering depends purely on
    stable deterministic tie-breakers, and no LLM tokens are spent."""

    model = "fake-llm"

    def chat(self, *, system_prompt: str, user_prompt: str) -> str:
        return json.dumps(
            {
                "overall_score": 80,
                "relevance_score": 80,
                "novelty_score": 80,
                "actionability_score": 80,
                "summary": "(fake)",
                "recommendation": "(fake)",
                "keywords": [],
            }
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pipeline diagnostic dry-run.")
    parser.add_argument("--hours", type=int, default=None, help="Override DIGEST_HOURS.")
    parser.add_argument(
        "--newsletter-threshold",
        type=int,
        default=1,
        help="Min number of newsletter (email-category) articles expected in raw fetch.",
    )
    parser.add_argument(
        "--final-topic-threshold",
        type=int,
        default=3,
        help="Min number of distinct topics expected in the final selection.",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    settings = Settings.from_env()
    hours = args.hours or settings.digest_hours
    updated_after = datetime.now(timezone.utc) - timedelta(hours=hours)
    allowed = settings.digest_topic_buckets
    buckets = settings.effective_buckets()

    _hr("Configuration")
    print(f"  hours                = {hours}")
    print(f"  buckets              = {buckets}")
    print(f"  candidate_limit      = {settings.digest_candidate_limit}")
    print(f"  pre_score_limit      = {settings.digest_pre_score_limit}")
    print(f"  top_n                = {settings.digest_top_n}")
    print(f"  max_per_site         = {settings.digest_max_per_site}")
    print(f"  max_per_author       = {settings.digest_max_per_author}")
    print(f"  topic_buckets        = {allowed}")

    readwise = ReadwiseClient(
        token=settings.readwise_token,
        base_url=settings.readwise_base_url,
        timeout_seconds=settings.request_timeout_seconds,
    )

    # --- Stage 1: raw fetch ------------------------------------------------
    _hr("Stage 1: raw fetch from Readwise")
    if settings.readwise_fetch_buckets:
        per_bucket: dict[str, int] = {}
        merged: dict[str, Article] = {}
        for b in buckets:
            sub = readwise.list_documents(
                updated_after=updated_after,
                location=b.location or settings.readwise_location,
                category=b.category,
                with_html_content=False,
                max_items=b.max_items,
            )
            label = b.category or "(all)"
            per_bucket[label] = len(sub)
            for article in sub:
                merged.setdefault(article.id, article)
        articles = list(merged.values())
        for label, count in per_bucket.items():
            print(f"  bucket category={label:<12} -> {count:>3} articles")
    else:
        articles = readwise.list_documents(
            updated_after=updated_after,
            location=settings.readwise_location,
            category=settings.readwise_category,
            with_html_content=False,
            max_items=settings.digest_candidate_limit,
        )
        per_bucket = {settings.readwise_category or "(all)": len(articles)}
    print(f"  total after merge    = {len(articles)} (deduped by document id)")
    _print_distribution("by category", _category_dist(articles))
    _print_distribution("by site", _site_dist(articles))
    _print_distribution("by content_type", _content_type_dist(articles))
    raw_topic_dist = _topic_dist(articles, allowed)
    _print_distribution("by topic", raw_topic_dist)

    # --- Stage 2: filter + pre-score diversity ----------------------------
    filtered = filter_articles(articles, hours=hours, max_candidates=settings.digest_candidate_limit)
    pre_scored = select_diverse_candidates(
        filtered,
        max_candidates=settings.digest_pre_score_limit,
        allowed_topics=allowed,
    )
    _hr("Stage 2: pre-score diversity pool")
    print(f"  filtered             = {len(filtered)}/{len(articles)}")
    print(f"  pre_scored           = {len(pre_scored)}/{len(filtered)}")
    _print_distribution("by topic", _topic_dist(pre_scored, allowed))
    _print_distribution("by site", _site_dist(pre_scored))
    _print_distribution("by author", _author_dist(pre_scored))

    # --- Stage 3: score + apply diversity ---------------------------------
    scored = score_articles(
        pre_scored,
        llm_client=_FakeLLM(),
        max_input_chars=settings.llm_max_input_chars,
        digest_language=settings.digest_language,
        scoring_focus=settings.digest_scoring_focus,
        top_n=settings.digest_top_n,
        llm_concurrency=1,
        max_per_site=settings.digest_max_per_site,
        max_per_author=settings.digest_max_per_author,
    )
    final_articles = [s.article for s in scored]
    final_topic_dist = _topic_dist(final_articles, allowed)
    final_site_dist = _site_dist(final_articles)
    final_author_dist = _author_dist(final_articles)
    final_ctype_dist = _content_type_dist(final_articles)

    final_publisher_dist = _publisher_dist(final_articles)
    _hr("Stage 3: final selection (top_n)")
    print(f"  final size           = {len(scored)}")
    _print_distribution("by topic", final_topic_dist)
    _print_distribution("by site (raw site_name)", final_site_dist)
    _print_distribution("by publisher (diversity key)", final_publisher_dist)
    _print_distribution("by author", final_author_dist)
    _print_distribution("by content_type", final_ctype_dist)
    print()
    for index, item in enumerate(scored, start=1):
        title = (item.article.title or "(untitled)")[:50]
        site = item.article.site_name or "?"
        cat = (item.article.category or "?").lower()
        ctype = content_type_for(item.article)
        topic = topic_for(item.article, allowed)
        print(f"  {index:>2}. [{topic:<8}/{ctype:<18}] {site[:18]:<18}  {title}  ({cat})")

    # --- Stage 4: self-checks ---------------------------------------------
    # Note: we evaluate publisher cap (the actual diversity dimension), not
    # raw site_name (which would false-alarm for WeChat's shared platform name).
    newsletter_count = per_bucket.get("email", _category_dist(articles).get("email", 0))
    publisher_offenders = {
        publisher: count
        for publisher, count in final_publisher_dist.items()
        if count > settings.digest_max_per_site
    }
    author_offenders = {
        author: count
        for author, count in final_author_dist.items()
        if count > settings.digest_max_per_author
    }
    final_has_newsletter = any(
        content_type_for(a) == "newsletter" or (a.category or "").lower() == "email"
        for a in final_articles
    )
    raw_topic_count = len(_topic_dist(articles, allowed))
    pre_topic_count = len(_topic_dist(pre_scored, allowed))
    final_topic_count = len(final_topic_dist)

    # Two upstream-aware notes that downgrade noise to "info" when relevant:
    upstream_no_email_note = (
        " (note: 0 email-category articles arrived in window; this is upstream, "
        "not a code issue. Newsletter sources may not have published yet, or you "
        "may need to wait for Readwise to ingest them.)"
        if newsletter_count == 0
        else ""
    )
    upstream_low_topic_note = (
        f" (note: only {raw_topic_count} topic(s) appeared in raw fetch within "
        f"the {hours}h window; pipeline cannot manufacture diversity that does "
        f"not exist upstream.)"
        if raw_topic_count < args.final_topic_threshold
        else ""
    )

    checks: list[tuple[bool, str]] = [
        (
            len(articles) > 0,
            f"raw fetch returned articles (total={len(articles)})",
        ),
        (
            newsletter_count >= args.newsletter_threshold,
            f"newsletter category present in raw fetch "
            f"(email={newsletter_count}, threshold={args.newsletter_threshold})"
            f"{upstream_no_email_note}",
        ),
        (
            pre_topic_count >= min(args.final_topic_threshold, raw_topic_count),
            f"pre-score pool covers all topics seen upstream "
            f"(pre={pre_topic_count}, raw={raw_topic_count})"
            f"{upstream_low_topic_note}",
        ),
        (
            final_topic_count >= min(args.final_topic_threshold, raw_topic_count),
            f"final selection covers all topics seen upstream "
            f"(final={final_topic_count}, raw={raw_topic_count})"
            f"{upstream_low_topic_note}",
        ),
        (
            not publisher_offenders,
            f"no publisher exceeds max_per_site={settings.digest_max_per_site} "
            f"(offenders={publisher_offenders or 'none'})",
        ),
        (
            not author_offenders and (final_has_newsletter or newsletter_count == 0),
            f"no author exceeds max_per_author={settings.digest_max_per_author}; "
            f"newsletter survived final cut iff any were available "
            f"(author_offenders={author_offenders or 'none'}, "
            f"newsletter_in_final={final_has_newsletter}, "
            f"newsletter_in_raw={newsletter_count})",
        ),
    ]

    _hr("Self-checks")
    failed = 0
    for ok, message in checks:
        marker = "[ OK ]" if ok else "[FAIL]"
        if not ok:
            failed += 1
        print(f"  {marker} {message}")

    print()
    distinct_publishers = len(final_publisher_dist)
    if failed == 0:
        print(
            f"  All {len(checks)} checks passed. "
            f"Distinct publishers in final cut: {distinct_publishers}."
        )
        return 0
    else:
        print(
            f"  {failed}/{len(checks)} check(s) failed. "
            "Many failures may reflect upstream conditions (no newsletter "
            "published yet, narrow topic mix in window). Re-read the notes "
            "next to each FAIL line before changing code or config."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
