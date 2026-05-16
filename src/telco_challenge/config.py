from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


DEFAULT_TRACK_A_URL = "https://124.71.227.61/no"
DEFAULT_TRACK_B_URL = "https://124.71.227.61/ip/api/agent/execute"


def load_project_env(path: str | Path = ".env") -> None:
    if load_dotenv is not None:
        load_dotenv(path, override=False)


def get_env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value or ""
