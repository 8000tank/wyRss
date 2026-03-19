from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
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


@dataclass(slots=True)
class Settings:
    readwise_token: str
    readwise_base_url: str
    readwise_location: str | None
    readwise_category: str | None
    readwise_with_html_content: bool
    request_timeout_seconds: int
    digest_hours: int
    digest_candidate_limit: int
    digest_top_n: int
    digest_output_dir: Path
    digest_language: str
    digest_scoring_focus: str
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_timeout_seconds: int
    llm_temperature: float
    llm_max_input_chars: int

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()

        readwise_token = os.getenv("READWISE_TOKEN", "").strip()
        llm_api_key = os.getenv("LLM_API_KEY", "").strip()
        llm_model = os.getenv("LLM_MODEL", "").strip()

        missing = [
            name
            for name, value in {
                "READWISE_TOKEN": readwise_token,
                "LLM_API_KEY": llm_api_key,
                "LLM_MODEL": llm_model,
            }.items()
            if not value
        ]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Missing required environment variables: {joined}")

        return cls(
            readwise_token=readwise_token,
            readwise_base_url=os.getenv("READWISE_BASE_URL", "https://readwise.io/api/v3").rstrip("/"),
            readwise_location=os.getenv("READWISE_LOCATION", "feed").strip() or None,
            readwise_category=os.getenv("READWISE_CATEGORY", "rss").strip() or None,
            readwise_with_html_content=_get_bool("READWISE_WITH_HTML_CONTENT", True),
            request_timeout_seconds=_get_int("REQUEST_TIMEOUT_SECONDS", 30),
            digest_hours=_get_int("DIGEST_HOURS", 24),
            digest_candidate_limit=_get_int("DIGEST_CANDIDATE_LIMIT", 30),
            digest_top_n=_get_int("DIGEST_TOP_N", 10),
            digest_output_dir=Path(os.getenv("DIGEST_OUTPUT_DIR", "output")),
            digest_language=os.getenv("DIGEST_LANGUAGE", "中文").strip() or "中文",
            digest_scoring_focus=os.getenv(
                "DIGEST_SCORING_FOCUS",
                "信息价值优先，其次考虑新颖度、可执行性和与技术/AI资讯的相关性。",
            ).strip(),
            llm_api_key=llm_api_key,
            llm_base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            llm_model=llm_model,
            llm_timeout_seconds=_get_int("LLM_TIMEOUT_SECONDS", 60),
            llm_temperature=_get_float("LLM_TEMPERATURE", 0.2),
            llm_max_input_chars=_get_int("LLM_MAX_INPUT_CHARS", 6000),
        )
