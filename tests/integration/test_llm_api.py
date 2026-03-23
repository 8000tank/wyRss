"""Integration tests for LLM API.

These tests make real API calls using the configured environment variables.
Run with: pytest tests/integration/test_llm_api.py -v
"""
from __future__ import annotations

import os

import pytest

from src.clients.llm_client import LLMClient
from src.config import Settings


@pytest.fixture
def real_llm_client() -> LLMClient:
    """Create an LLM client using real environment variables."""
    if not (
        os.getenv("RSS_LLM_API_KEY", "").strip()
        or os.getenv("LLM_API_KEY", "").strip()
    ):
        pytest.skip("RSS_LLM_API_KEY (or legacy LLM_API_KEY) not set")
    settings = Settings.from_env()
    return LLMClient(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        temperature=settings.llm_temperature,
    )


@pytest.mark.integration
class TestLLMAPI:
    """Integration tests for LLM API."""

    def test_basic_chat(self, real_llm_client: LLMClient) -> None:
        """Test basic chat completion with the configured LLM."""
        system_prompt = "You are a helpful assistant."
        user_prompt = "Say 'Hello, this is a test' and nothing else."

        try:
            response = real_llm_client.chat(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )

            assert isinstance(response, str)
            assert len(response) > 0
            print(f"\n✓ LLM chat test passed")
            print(f"  - Model: {real_llm_client.model}")
            print(f"  - Response preview: {response[:100]}...")
        except Exception as e:
            pytest.fail(f"Basic chat test failed: {e}")

    def test_chat_json_response(self, real_llm_client: LLMClient) -> None:
        """Test chat completion with JSON response extraction."""
        system_prompt = """You are a helpful assistant. Always respond with valid JSON.

Respond with a JSON object containing:
- "score": a number between 0 and 100
- "reason": a brief explanation string

Example: {"score": 85, "reason": "Good quality content"}"""

        user_prompt = "Rate this statement: 'The sky is blue on a clear day.'"

        try:
            result = real_llm_client.chat_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )

            assert isinstance(result, dict)
            assert "score" in result
            assert "reason" in result
            assert isinstance(result["score"], (int, float))
            assert 0 <= result["score"] <= 100

            print(f"\n✓ LLM JSON test passed")
            print(f"  - Model: {real_llm_client.model}")
            print(f"  - Parsed result: {result}")
        except Exception as e:
            pytest.fail(f"JSON chat test failed: {e}")

    def test_article_scoring_prompt(self, real_llm_client: LLMClient) -> None:
        """Test the actual article scoring prompt used in the pipeline."""
        system_prompt = (
            "你是一名严谨的资讯编辑。"
            "请根据文章内容输出一个 JSON 对象，不要输出额外解释。"
            "JSON 必须包含以下字段："
            "overall_score, relevance_score, novelty_score, actionability_score, summary, recommendation, keywords。"
            "其中四个分数字段必须是 0 到 100 的整数，summary 和 recommendation 使用简洁自然语言，"
            "keywords 是字符串数组，最多 5 个。"
        )

        user_prompt = """输出语言: 中文
排序目标: 信息价值优先

请重点判断这篇文章是否值得进入今天的资讯日报。

标题: AI技术突破：新模型在多项基准测试中超越人类水平
来源站点: TechNews
作者: 张三
原文链接: https://example.com/ai-breakthrough
发布时间: 2024-01-15
Readwise摘要: 一项新的AI研究展示了显著的性能提升
正文摘录:
研究人员宣布了一项重大突破，新开发的AI模型在多项基准测试中表现超越人类水平。这项技术可能彻底改变我们处理复杂任务的方式。模型采用了创新的架构设计，在推理能力和效率上都有显著提升。专家们认为这将对多个行业产生深远影响。"""

        try:
            result = real_llm_client.chat_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )

            required_fields = [
                "overall_score", "relevance_score", "novelty_score",
                "actionability_score", "summary", "recommendation", "keywords"
            ]

            for field in required_fields:
                assert field in result, f"Missing required field: {field}"

            # Validate score ranges
            for score_field in ["overall_score", "relevance_score", "novelty_score", "actionability_score"]:
                score = result[score_field]
                assert isinstance(score, (int, float)), f"{score_field} should be a number"
                assert 0 <= score <= 100, f"{score_field} should be between 0 and 100"

            assert isinstance(result["keywords"], list)
            assert len(result["keywords"]) <= 5

            print(f"\n✓ Article scoring test passed")
            print(f"  - Model: {real_llm_client.model}")
            print(f"  - Overall score: {result['overall_score']}")
            print(f"  - Summary: {result['summary'][:50]}...")
            print(f"  - Keywords: {result['keywords']}")
        except Exception as e:
            pytest.fail(f"Article scoring test failed: {e}")

    def test_chinese_output(self, real_llm_client: LLMClient) -> None:
        """Test that the LLM can output Chinese text correctly."""
        system_prompt = "你是一个助手。请用中文回复。"
        user_prompt = "请用一句话总结：人工智能正在快速发展。"

        try:
            response = real_llm_client.chat(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )

            assert isinstance(response, str)
            assert len(response) > 0
            # Check if response contains Chinese characters
            has_chinese = any('\u4e00' <= char <= '\u9fff' for char in response)

            print(f"\n✓ Chinese output test {'passed' if has_chinese else 'passed (but no Chinese detected)'}")
            print(f"  - Model: {real_llm_client.model}")
            print(f"  - Response: {response[:100]}...")
        except Exception as e:
            pytest.fail(f"Chinese output test failed: {e}")


@pytest.mark.skipif(
    not (
        os.getenv("RSS_LLM_API_KEY", "").strip()
        or os.getenv("LLM_API_KEY", "").strip()
    ),
    reason="RSS_LLM_API_KEY (or legacy LLM_API_KEY) not set",
)
def test_llm_configuration_loaded() -> None:
    """Test that LLM configuration can be loaded."""
    settings = Settings.from_env()
    assert settings.llm_api_key
    assert settings.llm_model
    assert settings.llm_base_url
    print(f"\n✓ LLM configuration loaded:")
    print(f"  - Base URL: {settings.llm_base_url}")
    print(f"  - Model: {settings.llm_model}")
    print(f"  - Temperature: {settings.llm_temperature}")
