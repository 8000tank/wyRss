"""Integration test for the full digest pipeline.

This test runs the entire workflow from fetching articles to generating the digest.
Run with: pytest tests/integration/test_full_pipeline.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.clients.llm_client import LLMClient
from src.clients.readwise_client import ReadwiseClient
from src.config import Settings
from src.pipeline.filtering import filter_articles
from src.pipeline.ranking import score_articles
from src.renderers.markdown_renderer import render_markdown, write_markdown


@pytest.mark.integration
class TestFullPipeline:
    """End-to-end integration test for the digest workflow."""

    def test_full_pipeline_run(self, tmp_path: Path) -> None:
        """Test the complete pipeline from fetch to digest generation."""
        print("\n" + "="*50)
        print("Starting full pipeline integration test")
        print("="*50)

        # Load configuration
        settings = Settings.from_env()
        print(f"\nConfiguration:")
        print(f"  - Readwise: {settings.readwise_base_url}")
        print(f"  - LLM: {settings.llm_base_url} ({settings.llm_model})")
        print(f"  - Time window: {settings.digest_hours} hours")
        print(f"  - Top N: {settings.digest_top_n}")

        # Step 1: Initialize clients
        print("\n[Step 1/5] Initializing clients...")
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
        print("  ✓ Clients initialized")

        # Step 2: Fetch articles from Readwise
        print(f"\n[Step 2/5] Fetching articles from Readwise...")
        print(f"  - Location: {settings.readwise_location}")
        print(f"  - Category: {settings.readwise_category}")

        updated_after = datetime.now(timezone.utc) - timedelta(hours=settings.digest_hours)

        try:
            articles = readwise_client.list_documents(
                updated_after=updated_after,
                location=settings.readwise_location,
                category=settings.readwise_category,
                with_html_content=settings.readwise_with_html_content,
                max_items=settings.digest_candidate_limit,
            )
            print(f"  ✓ Fetched {len(articles)} articles")

            if not articles:
                print("\n⚠ No articles found in the specified time window.")
                print("  Consider increasing DIGEST_HOURS or checking your Readwise account.")
                return

            # Show first few articles
            for i, article in enumerate(articles[:3], 1):
                print(f"    {i}. {article.title[:50]}... ({article.site_name or 'Unknown'})")
            if len(articles) > 3:
                print(f"    ... and {len(articles) - 3} more")

        except Exception as e:
            pytest.fail(f"Failed to fetch articles: {e}")

        # Step 3: Filter and deduplicate
        print(f"\n[Step 3/5] Filtering and deduplicating...")
        candidates = filter_articles(
            articles,
            hours=settings.digest_hours,
            max_candidates=settings.digest_candidate_limit,
        )
        print(f"  ✓ {len(candidates)} candidates after filtering")

        if not candidates:
            print("\n⚠ No candidates passed the filtering criteria.")
            return

        # Step 4: Score with LLM
        print(f"\n[Step 4/5] Scoring {len(candidates)} candidates with LLM...")
        print(f"  - Model: {settings.llm_model}")
        print(f"  - Language: {settings.digest_language}")

        try:
            scored_articles = score_articles(
                candidates,
                llm_client=llm_client,
                max_input_chars=settings.llm_max_input_chars,
                digest_language=settings.digest_language,
                scoring_focus=settings.digest_scoring_focus,
                top_n=settings.digest_top_n,
            )
            print(f"  ✓ Scored and selected top {len(scored_articles)} articles")

            for i, item in enumerate(scored_articles[:3], 1):
                print(f"    {i}. [{item.overall_score}] {item.article.title[:40]}...")
            if len(scored_articles) > 3:
                print(f"    ... and {len(scored_articles) - 3} more")

        except Exception as e:
            pytest.fail(f"Failed to score articles: {e}")

        # Step 5: Generate and save digest
        print(f"\n[Step 5/5] Generating digest...")
        generated_at = datetime.now(timezone.utc)

        markdown = render_markdown(
            generated_at=generated_at,
            hours=settings.digest_hours,
            fetched_count=len(articles),
            candidate_count=len(candidates),
            scored_articles=scored_articles,
        )

        output_dir = tmp_path / "test_output"
        output_path = write_markdown(output_dir, generated_at, markdown)

        print(f"  ✓ Digest saved to: {output_path}")
        print(f"  - File size: {output_path.stat().st_size} bytes")

        # Verify output
        assert output_path.exists()
        assert output_path.stat().st_size > 0

        # Print summary
        content = output_path.read_text(encoding="utf-8")
        print(f"\n{'='*50}")
        print("Pipeline test completed successfully!")
        print(f"{'='*50}")
        print(f"\nDigest preview (first 500 chars):")
        print("-" * 50)
        print(content[:500])
        print("-" * 50)

        # Save to actual output directory as well
        real_output = settings.digest_output_dir
        real_output.mkdir(parents=True, exist_ok=True)
        real_path = real_output / f"readwise-digest-{generated_at.strftime('%Y-%m-%d')}-test.md"
        real_path.write_text(markdown, encoding="utf-8")
        print(f"\nAlso saved to: {real_path}")
