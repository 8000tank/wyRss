"""Unit tests for the OpenAI-compatible LLM client."""
from __future__ import annotations

import json

import responses

from src.clients.llm_client import LLMClient


@responses.activate
def test_chat_uses_configured_max_tokens() -> None:
    responses.post(
        "https://api.example.com/v1/chat/completions",
        json={
            "choices": [
                {
                    "message": {
                        "content": "ok",
                    },
                },
            ],
        },
        status=200,
    )
    client = LLMClient(
        api_key="test-key",
        base_url="https://api.example.com/v1",
        model="test-model",
        max_tokens=8192,
    )

    result = client.chat(system_prompt="system", user_prompt="user")

    assert result == "ok"
    body = json.loads(responses.calls[0].request.body)
    assert body["max_tokens"] == 8192


@responses.activate
def test_chat_merges_provider_extra_body() -> None:
    responses.post(
        "https://api.example.com/v1/chat/completions",
        json={
            "choices": [
                {
                    "message": {
                        "content": "{}",
                    },
                },
            ],
        },
        status=200,
    )
    client = LLMClient(
        api_key="test-key",
        base_url="https://api.example.com/v1",
        model="test-model",
        extra_body={"reasoning_split": True},
    )

    client.chat(system_prompt="system", user_prompt="user")

    body = json.loads(responses.calls[0].request.body)
    assert body["reasoning_split"] is True
