from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class ApiResponse:
    status_code: int
    payload: Any
    text: str


class ChallengeSession:
    def __init__(self, token: str, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            }
        )

    def get(self, url: str, **kwargs: Any) -> ApiResponse:
        response = self.session.get(url, timeout=self.timeout, verify=False, **kwargs)
        return _to_api_response(response)

    def post(self, url: str, **kwargs: Any) -> ApiResponse:
        response = self.session.post(url, timeout=self.timeout, verify=False, **kwargs)
        return _to_api_response(response)


def _to_api_response(response: requests.Response) -> ApiResponse:
    try:
        payload: Any = response.json()
    except ValueError:
        payload = None
    return ApiResponse(status_code=response.status_code, payload=payload, text=response.text)

