from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from telco_challenge.model_client import ChatClient
from telco_challenge.track_a import TrackAClient


ENDPOINTS = ["throughput_logs", "config_data", "kpi_data", "mr_data"]


@dataclass(frozen=True)
class TrackASolveResult:
    scenario_id: str
    prediction: str
    raw_response: str
    evidence_count: int


class TrackASolver:
    def __init__(self, api_client: TrackAClient, model_client: ChatClient, max_evidence_chars: int = 14000) -> None:
        self.api_client = api_client
        self.model_client = model_client
        self.max_evidence_chars = max_evidence_chars

    def solve(self, row: dict) -> TrackASolveResult:
        scenario_id = row["scenario_id"]
        evidence = self.collect_evidence(scenario_id)
        prompt = build_prompt(row, evidence, self.max_evidence_chars)
        raw_response = self.model_client.complete(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=700,
        )
        prediction = extract_track_a_answer(raw_response, row)
        if not prediction:
            repaired = repair_prompt(row, raw_response)
            raw_response = self.model_client.complete(
                [{"role": "user", "content": repaired}],
                temperature=0.0,
                max_tokens=128,
            )
            prediction = extract_track_a_answer(raw_response, row)
        return TrackASolveResult(scenario_id, prediction, raw_response, len(evidence))

    def collect_evidence(self, scenario_id: str) -> dict[str, Any]:
        evidence: dict[str, Any] = {}
        for endpoint in ENDPOINTS:
            try:
                evidence[endpoint] = self.api_client.call(endpoint, scenario_id=scenario_id)
            except Exception as exc:
                evidence[endpoint] = {"error": str(exc)}
        return evidence


def build_prompt(row: dict, evidence: dict[str, Any], max_chars: int) -> str:
    options = "\n".join(f"{option['id']}: {option['label']}" for option in row["task"]["options"])
    evidence_text = json.dumps(evidence, ensure_ascii=False)
    if len(evidence_text) > max_chars:
        evidence_text = evidence_text[:max_chars] + "\n...[truncated]"
    return (
        "/no_think\n"
        "Analyze the wireless troubleshooting evidence and choose the best option labels.\n"
        "Return only the final answer in the format \\boxed{C3} or \\boxed{C3|C5}. Do not explain.\n\n"
        f"Question:\n{row['task']['description']}\n\n"
        f"Options:\n{options}\n\n"
        f"Evidence:\n{evidence_text}\n\n"
        "Final answer:"
    )


def repair_prompt(row: dict, raw_response: str) -> str:
    options = ", ".join(option["id"] for option in row["task"]["options"])
    return (
        "/no_think\n"
        "Extract only the option labels from the response.\n"
        f"Allowed labels: {options}\n"
        "Return only \\boxed{...} with one label for single-answer questions or two to four labels for multiple-answer questions.\n\n"
        f"Response:\n{raw_response}\n"
    )


def extract_track_a_answer(text: str, row: dict) -> str:
    allowed = {option["id"] for option in row["task"]["options"]}
    boxed = re.findall(r"\\boxed\{([^{}]+)\}", text)
    candidates = boxed if boxed else re.findall(r"\bC\d+(?:\|C\d+){0,3}\b", text.upper())
    if not candidates:
        return ""
    labels = [label for label in re.findall(r"C\d+", candidates[-1].upper()) if label in allowed]
    if row.get("tag") == "multiple-answer":
        labels = labels[:4]
        if len(labels) < 2:
            return ""
    else:
        labels = labels[:1]
    return "|".join(labels)


def append_track_a_trace(path: str | Path, result: TrackASolveResult) -> None:
    trace_path = Path(path)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result.__dict__, ensure_ascii=False) + "\n")
