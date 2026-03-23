from __future__ import annotations

import json
import re
import threading
from typing import Any

import requests


class LLMClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: int = 60,
        temperature: float = 0.2,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._thread_local = threading.local()

    def _get_session(self) -> requests.Session:
        session = getattr(self._thread_local, "session", None)
        if session is None:
            session = requests.Session()
            session.headers.update(self._headers)
            self._thread_local.session = session
        return session

    def chat(self, *, system_prompt: str, user_prompt: str) -> str:
        response = self._get_session().post(
            f"{self.base_url}/chat/completions",
            timeout=self.timeout_seconds,
            json={
                "model": self.model,
                "temperature": self.temperature,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"].strip()

    def chat_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        content = self.chat(system_prompt=system_prompt, user_prompt=user_prompt)
        return self._extract_json(content)

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, flags=re.DOTALL)
        candidate = fenced_match.group(1) if fenced_match else content

        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            first_brace = candidate.find("{")
            last_brace = candidate.rfind("}")
            if first_brace == -1 or last_brace == -1 or last_brace <= first_brace:
                raise ValueError("LLM response does not contain valid JSON.") from None
            return json.loads(candidate[first_brace : last_brace + 1])
