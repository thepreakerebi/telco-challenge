from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
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
    cache_dir: str | Path | None = None

    def __post_init__(self) -> None:
        self.server_url = self.server_url.rstrip("/")
        self.session = ChallengeSession(self.token, timeout=self.timeout)
        self.cache_root = Path(self.cache_dir) if self.cache_dir else None

    def call(
        self,
        endpoint_name: str,
        scenario_id: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        params = params or {}
        cache_path = self._cache_path(endpoint_name, scenario_id, params)
        if cache_path and cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))

        endpoint = TRACK_A_ENDPOINTS.get(endpoint_name, endpoint_name)
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        headers = {}
        if scenario_id:
            headers["X-Scenario-Id"] = scenario_id
            headers["X-API-Token"] = self.token
        response = self.session.get(f"{self.server_url}{endpoint}", params=params, headers=headers)
        if response.status_code >= 400:
            raise RuntimeError(f"Track A request failed: {response.status_code} {response.text[:500]}")
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(response.payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return response.payload

    def _cache_path(self, endpoint_name: str, scenario_id: str | None, params: dict[str, Any]) -> Path | None:
        if self.cache_root is None or endpoint_name == "tools":
            return None
        payload = json.dumps({"endpoint": endpoint_name, "scenario_id": scenario_id, "params": params}, sort_keys=True)
        digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
        scenario_part = scenario_id or "global"
        return self.cache_root / scenario_part / f"{endpoint_name}_{digest}.json"
