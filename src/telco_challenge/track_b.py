from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from telco_challenge.http import ChallengeSession


@dataclass(frozen=True)
class CommandResult:
    question_number: int
    device_name: str
    command: str
    status_code: int
    output: str
    payload: Any


class TrackBClient:
    def __init__(self, endpoint_url: str, token: str, timeout: float = 30.0) -> None:
        self.endpoint_url = endpoint_url
        self.session = ChallengeSession(token, timeout=timeout)

    def execute(self, question_number: int, device_name: str, command: str) -> CommandResult:
        body = {
            "question_number": question_number,
            "device_name": device_name,
            "command": command,
        }
        response = self.session.post(self.endpoint_url, json=body)
        output = _extract_output(response.payload, response.text)
        return CommandResult(
            question_number=question_number,
            device_name=device_name,
            command=command,
            status_code=response.status_code,
            output=output,
            payload=response.payload,
        )


class LocalTrackBOutputs:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def execute(self, question_number: int, device_name: str, command: str) -> CommandResult:
        path = self.root / str(question_number) / device_name / f"{_safe_command_name(command)}.txt"
        if not path.exists():
            return CommandResult(question_number, device_name, command, 404, "", {"error": f"Missing output: {path}"})
        output = path.read_text(encoding="utf-8")
        return CommandResult(question_number, device_name, command, 200, output, {"output": output})

    def devices(self, question_number: int) -> list[str]:
        question_dir = self.root / str(question_number)
        if not question_dir.exists():
            return []
        return sorted(path.name for path in question_dir.iterdir() if path.is_dir())

    def commands(self, question_number: int, device_name: str) -> list[str]:
        device_dir = self.root / str(question_number) / device_name
        if not device_dir.exists():
            return []
        return sorted(path.stem for path in device_dir.glob("*.txt"))


def append_trace(path: str | Path, result: CommandResult, source: str) -> None:
    trace_path = Path(path)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "question_number": result.question_number,
        "device_name": result.device_name,
        "command": result.command,
        "status_code": result.status_code,
        "payload": result.payload,
    }
    with trace_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _safe_command_name(command: str) -> str:
    return command.replace("/", "-").replace(" ", "_")


def _extract_output(payload: Any, text: str) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("output", "result", "data", "message"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
        return json.dumps(payload, ensure_ascii=False)
    return text

