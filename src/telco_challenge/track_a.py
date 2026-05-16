from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from telco_challenge.http import ChallengeSession


TRACK_A_ENDPOINTS = {
    "tools": "/tools",
    "scenario": "/scenario",
    "all_scenarios": "/scenario/all",
    "config_data": "/config-data",
    "user_plane_data": "/user-plane-data",
    "throughput_logs": "/throughput-logs",
    "cell_info": "/cell-info",
    "kpi_data": "/get_kpi_data",
    "mr_data": "/get_mr_data",
}


@dataclass
class TrackAClient:
    server_url: str
    token: str
    timeout: float = 30.0

    def __post_init__(self) -> None:
        self.server_url = self.server_url.rstrip("/")
        self.session = ChallengeSession(self.token, timeout=self.timeout)

    def call(
        self,
        endpoint_name: str,
        scenario_id: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        endpoint = TRACK_A_ENDPOINTS.get(endpoint_name, endpoint_name)
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        headers = {}
        if scenario_id:
            headers["X-Scenario-Id"] = scenario_id
            headers["X-API-Token"] = self.token
        response = self.session.get(f"{self.server_url}{endpoint}", params=params or {}, headers=headers)
        if response.status_code >= 400:
            raise RuntimeError(f"Track A request failed: {response.status_code} {response.text[:500]}")
        return response.payload

