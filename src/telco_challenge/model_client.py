from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class ChatClient:
    base_url: str
    api_key: str
    model_name: str
    timeout: float = 120.0

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )

    def complete(self, messages: list[dict[str, str]], temperature: float = 0.0, max_tokens: int = 512) -> str:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "reasoning": {
                "effort": "none",
                "exclude": True,
            },
        }
        response = self.session.post(f"{self.base_url}/chat/completions", json=payload, timeout=self.timeout)
        if response.status_code >= 400:
            raise RuntimeError(f"Model request failed: {response.status_code} {response.text[:500]}")
        data = response.json()
        message = data["choices"][0]["message"]
        return extract_message_text(message)


def extract_message_text(message: dict[str, Any]) -> str:
    for key in ("content", "reasoning", "reasoning_content"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, list):
            text = "\n".join(part.get("text", "") for part in value if isinstance(part, dict))
            if text.strip():
                return text
    return ""
