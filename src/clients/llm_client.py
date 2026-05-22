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
        max_tokens: int = 4096,
        extra_body: dict[str, Any] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.extra_body = extra_body or {}
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
        request_body: dict[str, Any] = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        request_body.update(self.extra_body)

        response = self._get_session().post(
            f"{self.base_url}/chat/completions",
            timeout=self.timeout_seconds,
            json=request_body,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"].strip()

    def chat_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        content = self.chat(system_prompt=system_prompt, user_prompt=user_prompt)
        return self._extract_json(content)

    @staticmethod
    def _repair_json_string(text: str) -> str:
        """Try to fix common LLM JSON output issues before parsing."""
        # Strip markdown fences
        fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
        candidate = fenced_match.group(1) if fenced_match else text

        # Extract JSON object boundaries
        first_brace = candidate.find("{")
        last_brace = candidate.rfind("}")
        if first_brace == -1:
            return candidate

        if last_brace == -1 or last_brace <= first_brace:
            candidate = candidate[first_brace:]
        else:
            candidate = candidate[first_brace : last_brace + 1]

        # Remove control characters (except \n, \r, \t)
        candidate = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', candidate)

        return candidate

    @staticmethod
    def _extract_json_fields_regex(text: str) -> dict[str, Any] | None:
        """Last-resort field extraction using regex when json.loads fails.
        
        Handles:
        - Unescaped double quotes inside string values (e.g. "特朗普-耶稣" in a JSON string)
        - Truncated JSON output
        """
        first_brace = text.find("{")
        if first_brace == -1:
            return None
        last_brace = text.rfind("}")
        body = text[first_brace + 1 : last_brace] if last_brace > first_brace else text[first_brace + 1 :]

        result: dict[str, Any] = {}
        pos = 0

        while pos < len(body):
            # Find next key: "key_name":
            m = re.search(r'"([a-z_]+)"\s*:', body[pos:])
            if not m:
                break
            
            key = m.group(1)
            val_start = pos + m.end()

            # Skip whitespace
            while val_start < len(body) and body[val_start] in ' \t\n\r':
                val_start += 1
            if val_start >= len(body):
                break

            val_char = body[val_start]

            if val_char == '"':
                # String value with potentially embedded unescaped quotes.
                # The REAL closing quote is followed by: , or } or ] or end-of-body,
                # possibly with whitespace in between.
                scan = val_start + 1
                close_quote = -1
                while scan < len(body):
                    if body[scan] == '\\':
                        scan += 2
                        continue
                    if body[scan] == '"':
                        # Check if this is the real closing quote
                        rest = body[scan + 1:].lstrip()
                        if (not rest
                            or rest[0] in ',}]'
                            or re.match(r'"[a-z_]+', rest)):
                            close_quote = scan
                            break
                    scan += 1

                if close_quote == -1:
                    # No closing quote found (truncated) — take everything until
                    # the next key pattern or end of body
                    next_key = re.search(r'\n\s*"[a-z_]+\"\s*:', body[scan:])
                    if next_key:
                        raw_val = body[val_start + 1 : scan + next_key.start()]
                    else:
                        raw_val = body[val_start + 1:]
                    result[key] = raw_val.strip().rstrip(",")
                    break  # can't reliably parse more after truncation
                else:
                    raw_val = body[val_start + 1 : close_quote]
                    raw_val = raw_val.replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t")
                    result[key] = raw_val
                    pos = close_quote + 1

            elif val_char == '[':
                depth = 1
                arr_end = val_start + 1
                in_str = False
                while arr_end < len(body) and depth > 0:
                    ch = body[arr_end]
                    if ch == '\\' and in_str:
                        arr_end += 2
                        continue
                    if ch == '"' and not in_str:
                        in_str = True
                    elif ch == '"' and in_str:
                        # Check if real close
                        rest = body[arr_end + 1:].lstrip()
                        if not rest or rest[0] in ',]}':
                            in_str = False
                    elif not in_str:
                        if ch == '[': depth += 1
                        elif ch == ']': depth -= 1
                    arr_end += 1
                arr_str = body[val_start:arr_end]
                try:
                    result[key] = json.loads(arr_str)
                except json.JSONDecodeError:
                    result[key] = re.findall(r'"([^"]*)"', arr_str)
                pos = arr_end

            elif val_char in '0123456789-':
                m2 = re.match(r'-?\d+(\.\d+)?', body[val_start:])
                if m2:
                    vs = m2.group()
                    result[key] = float(vs) if '.' in vs else int(vs)
                    pos = val_start + len(vs)
                else:
                    pos = val_start + 1
            elif body[val_start:val_start + 4] == "true":
                result[key] = True; pos = val_start + 4
            elif body[val_start:val_start + 5] == "false":
                result[key] = False; pos = val_start + 5
            elif body[val_start:val_start + 4] == "null":
                result[key] = None; pos = val_start + 4
            else:
                pos = val_start + 1

        return result if result else None

    @staticmethod
    def _normalize_keys(payload: dict[str, Any]) -> dict[str, Any]:
        """Normalize JSON keys to lowercase snake_case.

        LLMs sometimes produce slight case variations in field names
        (e.g. ``noveltY_score`` instead of ``novelty_score``).  This helper
        lowercases every top-level key so downstream validation can match
        against the expected canonical names.
        """
        return {k.lower(): v for k, v in payload.items()}

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        # Try 1: repair + json.loads
        candidate = LLMClient._repair_json_string(content)
        try:
            parsed = json.loads(candidate)
            return LLMClient._normalize_keys(parsed)
        except json.JSONDecodeError:
            pass

        # Try 2: regex field extraction
        extracted = LLMClient._extract_json_fields_regex(content)
        if extracted:
            return LLMClient._normalize_keys(extracted)

        raise ValueError(f"Failed to parse LLM JSON response: {candidate[:300]}") from None
