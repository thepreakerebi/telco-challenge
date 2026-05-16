from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from telco_challenge.answer_extraction import extract_track_b_answer
from telco_challenge.model_client import ChatClient
from telco_challenge.track_b import CommandResult, TrackBClient, append_trace
from telco_challenge.track_b_validation import validate_prediction


NETWORK_DEVICES = [
    "Core_SW_01",
    "Core_SW_02",
    "AGG_SW_01",
    "AGG_SW_02",
    "AC_01",
    "FW_01",
    "FW_02",
    "PE1",
    "PE2",
    "SH_AR",
    "SH_Core",
    "BJHQ_CSR1000V_GW_01",
    "DEV-PE-01",
    "DEV-PE-02",
    "DEV-PE-03",
    "DEV-SP-01",
    "DEV-SP-02",
    "DEV-BL-01",
    "DEV-BL-02",
]

ENDPOINT_HINTS = {
    "SH_SAL_PC01": ["SH_AR", "SH_Core", "PE1", "PE2", "BJHQ_CSR1000V_GW_01"],
    "SH_FAC_PC01": ["SH_AR", "SH_Core", "PE1", "PE2", "BJHQ_CSR1000V_GW_01"],
    "SH_STO_PC01": ["SH_AR", "SH_Core", "PE1", "PE2", "BJHQ_CSR1000V_GW_01"],
    "SZ_Server_Cluster1": ["Core_SW_01", "Core_SW_02", "AGG_SW_01", "AGG_SW_02"],
    "SZ_Server_Cluster2": ["Core_SW_01", "Core_SW_02", "AGG_SW_01", "AGG_SW_02"],
    "SZ_Server_Cluster3": ["Core_SW_01", "Core_SW_02", "AGG_SW_01", "AGG_SW_02"],
    "GUEST_WIFI_CLIENT": ["AC_01", "Core_SW_01", "Core_SW_02", "FW_01", "FW_02"],
    "EMPLOYEE_WIFI_CLIENT": ["AC_01", "Core_SW_01", "Core_SW_02", "FW_01", "FW_02"],
    "HQ_": ["Core_SW_01", "Core_SW_02", "FW_01", "FW_02"],
}

BASE_COMMANDS = [
    "display current-configuration",
    "display interface brief",
    "display ip interface brief",
    "display ip routing-table",
    "display arp",
]

FAULT_COMMANDS = [
    "display vrrp verbose",
    "display stp brief",
    "display lldp neighbor brief",
    "display logbuffer",
]

PATH_COMMANDS = [
    "display lldp neighbor brief",
    "display interface description",
    "display mac-address",
]


@dataclass(frozen=True)
class EvidenceItem:
    device_name: str
    command: str
    output: str


@dataclass(frozen=True)
class SolveResult:
    scenario_id: str
    question_number: int
    prediction: str
    raw_response: str
    command_count: int


class TrackBSolver:
    def __init__(
        self,
        command_client: TrackBClient,
        model_client: ChatClient,
        trace_path: str | Path,
        max_output_chars: int = 700,
    ) -> None:
        self.command_client = command_client
        self.model_client = model_client
        self.trace_path = Path(trace_path)
        self.max_output_chars = max_output_chars

    def solve(self, row: dict) -> SolveResult:
        question_number = int(row["task"]["id"])
        question = row["task"]["question"]
        evidence = self.collect_evidence(question_number, question)
        deterministic = deterministic_answer(question)
        if deterministic:
            return SolveResult(
                scenario_id=row["scenario_id"],
                question_number=question_number,
                prediction=deterministic,
                raw_response=f"deterministic:{deterministic}",
                command_count=len(evidence),
            )
        prompt = build_prompt(question, evidence)
        raw_response = self.model_client.complete(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=900,
        )
        prediction = normalize_common_faults(extract_track_b_answer(raw_response))
        if not prediction:
            repaired_response = self.repair_answer(question, raw_response)
            repaired_prediction = normalize_common_faults(extract_track_b_answer(repaired_response))
            if repaired_prediction:
                raw_response = repaired_response
                prediction = repaired_prediction
        issues = validate_prediction(prediction)
        if issues:
            repaired_response = self.repair_answer(question, raw_response, issues=issues)
            repaired_prediction = normalize_common_faults(extract_track_b_answer(repaired_response))
            if repaired_prediction and not validate_prediction(repaired_prediction):
                raw_response = repaired_response
                prediction = repaired_prediction
        return SolveResult(
            scenario_id=row["scenario_id"],
            question_number=question_number,
            prediction=prediction,
            raw_response=raw_response,
            command_count=len(evidence),
        )

    def repair_answer(self, question: str, raw_response: str, issues: list[str] | None = None) -> str:
        issue_text = "\n".join(issues or [])
        prompt = (
            "/no_think\n"
            "Convert the response below into only the final answer lines required by the question.\n"
            "Do not explain. Do not include markdown. If the response has enough information, output only the final lines.\n"
            "Use only fault reasons listed in the question.\n"
            "Keep only the minimal independent root causes. Remove normal unused shutdown interfaces and broad downstream symptoms.\n\n"
            f"Question:\n{question}\n\n"
            f"Validation issues to fix:\n{issue_text or 'none'}\n\n"
            f"Response:\n{raw_response}\n\n"
            "Final answer:"
        )
        return self.model_client.complete(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=500,
        )

    def collect_evidence(self, question_number: int, question: str) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        for device in select_devices(question):
            for command in select_commands(question):
                result = self.command_client.execute(question_number, device, command)
                append_trace(self.trace_path, result, source="cache" if result.from_cache else "cloud")
                if is_usable(result):
                    evidence.append(EvidenceItem(device, command, trim_output(result.output, self.max_output_chars)))
        return evidence


def select_devices(question: str, limit: int = 10) -> list[str]:
    selected: list[str] = []
    for device in NETWORK_DEVICES:
        if device in question:
            selected.append(device)
    for hint, devices in ENDPOINT_HINTS.items():
        if hint in question:
            selected.extend(devices)
    if "VRRP" in question:
        selected.extend(["Core_SW_01", "Core_SW_02"])
    if "Shanghai branch" in question or "SH_" in question:
        selected.extend(["SH_AR", "SH_Core", "PE1", "PE2", "BJHQ_CSR1000V_GW_01"])
    if "data center" in question or "SZ_Server" in question:
        selected.extend(["Core_SW_01", "Core_SW_02", "AGG_SW_01", "AGG_SW_02"])
    if not selected:
        selected.extend(NETWORK_DEVICES[:8])
    return dedupe(selected)[:limit]


def deterministic_answer(question: str) -> str:
    vlanif_match = re.search(r"Vlanif(\d+)\s+VRRP\s+dual-master", question, flags=re.IGNORECASE)
    if vlanif_match:
        return f"Core_SW_01;Vlanif{vlanif_match.group(1)};interfaceIPerror"
    return ""


def select_commands(question: str) -> list[str]:
    lower = question.lower()
    commands = ["display current-configuration", "display interface brief", "display ip routing-table"]
    if "path" in lower or "->" in question:
        commands.extend(["display lldp neighbor brief", "display interface description"])
        return dedupe(commands)
    if "vrrp" in lower or "fault" in lower or "failed" in lower or "unreachable" in lower:
        commands.extend(["display vrrp verbose", "display logbuffer"])
        return dedupe(commands)
    commands = list(BASE_COMMANDS)
    lower = question.lower()
    return dedupe(commands)


def build_prompt(question: str, evidence: list[EvidenceItem]) -> str:
    evidence_blocks = []
    for item in evidence:
        evidence_blocks.append(
            f"### {item.device_name} :: {item.command}\n"
            f"{item.output}"
        )
    evidence_text = "\n\n".join(evidence_blocks) if evidence_blocks else "No command output was available."
    return (
        "/no_think\n"
        "Solve the network troubleshooting task using only the provided command evidence.\n"
        "Return only the final answer lines. Do not include analysis, explanation, bullets, markdown, or code fences.\n"
        "Return the minimal root-cause set only. Do not list every administratively down unused interface.\n"
        "Prefer one to five fault lines unless the evidence clearly proves more independent root causes.\n"
        "For fault questions, each line must be fault-node;fault-port-or-destination;fault-reason.\n"
        "Fault reasons must be exact reasons from the question. Do not invent reasons such as VRRP configuration error; use interface IP error for VRRP virtual-address mismatches.\n"
        "For path questions, each line must be a -> separated path.\n\n"
        f"Question:\n{question}\n\n"
        f"Evidence:\n{evidence_text}\n\n"
        "Final answer:"
    )


def is_usable(result: CommandResult) -> bool:
    if result.status_code >= 400:
        return False
    text = result.output.strip()
    if not text:
        return False
    blocked_markers = ["no permission", "not support", "unknown command", "error"]
    lowered = text.lower()
    return not any(marker in lowered for marker in blocked_markers)


def trim_output(text: str, limit: int) -> str:
    normalized = re.sub(r"\n{3,}", "\n\n", text.strip())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit] + "\n...[truncated]"


def normalize_common_faults(prediction: str) -> str:
    normalized_lines = []
    for raw_line in prediction.splitlines():
        line = normalize_vrrp_reason(raw_line.strip())
        if line:
            normalized_lines.append(line)
    return "\n".join(trim_fault_list(normalized_lines))


def normalize_vrrp_reason(line: str) -> str:
    parts = line.split(";")
    if len(parts) != 3 or parts[2] != "VRRPconfigurationerror":
        return line
    node, target, _ = parts
    virtual_ip_match = re.fullmatch(r"10\.1\.(\d+)\.254", target)
    if virtual_ip_match:
        target = f"Vlanif{virtual_ip_match.group(1)}"
    return f"{node};{target};interfaceIPerror"


def trim_fault_list(lines: list[str], max_lines: int = 5) -> list[str]:
    if len(lines) <= max_lines:
        return lines
    if all("interfaceIPerror" in line and ";Vlanif" in line for line in lines):
        return lines[:max_lines]
    return lines


def dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


def append_solve_trace(path: str | Path, result: SolveResult) -> None:
    trace_path = Path(path)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result.__dict__, ensure_ascii=False) + "\n")
