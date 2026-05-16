from __future__ import annotations

import json
import re
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd

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
            max_tokens=300,
        )
        prediction = extract_track_a_answer(raw_response, row)
        if not prediction:
            repaired = repair_prompt(row, raw_response)
            raw_response = self.model_client.complete(
                [{"role": "user", "content": repaired}],
                temperature=0.0,
                max_tokens=96,
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
    summary = summarize_evidence(evidence)
    option_diagnostics = summarize_options(row, evidence)
    evidence_text = json.dumps(evidence, ensure_ascii=False)
    if len(evidence_text) > max_chars:
        evidence_text = evidence_text[:max_chars] + "\n...[truncated]"
    return (
        "/no_think\n"
        "Analyze the wireless troubleshooting evidence and choose the best option labels.\n"
        "Use the structured diagnostics and option diagnostics before the raw evidence.\n"
        "Return only the final answer in the format \\boxed{C3} or \\boxed{C3|C5}. Do not explain.\n\n"
        f"Question:\n{row['task']['description']}\n\n"
        f"Options:\n{options}\n\n"
        f"Structured diagnostics:\n{summary}\n\n"
        f"Option diagnostics:\n{option_diagnostics}\n\n"
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


def summarize_evidence(evidence: dict[str, Any]) -> str:
    sections = []
    throughput = read_table(evidence.get("throughput_logs", {}), "Logs")
    if throughput is not None and not throughput.empty:
        value_column = "5G KPI PCell Layer2 MAC DL Throughput [Mbps]"
        throughput[value_column] = pd.to_numeric(throughput[value_column], errors="coerce")
        low = throughput.nsmallest(min(4, len(throughput)), value_column)
        sections.append(
            "Throughput: "
            f"min={throughput[value_column].min():.2f}, "
            f"mean={throughput[value_column].mean():.2f}, "
            f"low_points={low.to_dict(orient='records')}"
        )

    config = read_table(evidence.get("config_data", {}), "Network Configuration Data")
    if config is not None and not config.empty:
        keep = [
            "gNodeB ID",
            "Cell ID",
            "PCI",
            "Mechanical Azimuth",
            "Mechanical Downtilt",
            "Digital Tilt",
            "Height",
            "Transmission Power",
            "IntraFreqHoA3Offset [0.5dB]",
            "PdcchOccupiedSymbolNum",
        ]
        sections.append(f"Config: {config[[column for column in keep if column in config.columns]].to_dict(orient='records')}")

    kpi = read_table(evidence.get("kpi_data", {}), "Traffic Data")
    if kpi is not None and not kpi.empty:
        keep = [
            "gNodeB_ID",
            "Cell_ID",
            "Downlink PRB utilization(%)",
            "User Downlink Throughput(Mbps)",
            "Downlink Weak Coversge Ratio",
            "Downlink CCE Allocation Success Rate(%)",
        ]
        sections.append(f"KPI: {kpi[[column for column in keep if column in kpi.columns]].to_dict(orient='records')}")

    mr = read_table(evidence.get("mr_data", {}), "MR Data")
    if mr is not None and not mr.empty:
        sections.append(f"MR: {summarize_mr(mr)}")

    return "\n".join(sections)


def summarize_options(row: dict, evidence: dict[str, Any]) -> str:
    config = read_table(evidence.get("config_data", {}), "Network Configuration Data")
    kpi = read_table(evidence.get("kpi_data", {}), "Traffic Data")
    mr = read_table(evidence.get("mr_data", {}), "MR Data")
    cell_profiles = build_cell_profiles(config, kpi, mr)
    rows = []
    for option in row["task"]["options"]:
        label = option["label"]
        profile = option_profile(label, cell_profiles, config)
        rows.append(f"{option['id']}: {label} | {profile}")
    return "\n".join(rows)


def build_cell_profiles(
    config: pd.DataFrame | None,
    kpi: pd.DataFrame | None,
    mr: pd.DataFrame | None,
) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    pci_to_cell: dict[int, str] = {}
    if config is not None and not config.empty:
        for column in ["gNodeB ID", "Cell ID", "PCI", "Transmission Power", "PdcchOccupiedSymbolNum", "IntraFreqHoA3Offset [0.5dB]"]:
            if column in config.columns and column not in {"PdcchOccupiedSymbolNum"}:
                config[column] = pd.to_numeric(config[column], errors="coerce")
        for _, record in config.iterrows():
            cell_key = make_cell_key(record.get("gNodeB ID"), record.get("Cell ID"))
            if not cell_key:
                continue
            pci = record.get("PCI")
            if pd.notna(pci):
                pci_to_cell[int(pci)] = cell_key
            profiles[cell_key] = {
                "pci": int(pci) if pd.notna(pci) else None,
                "tx_power": record.get("Transmission Power"),
                "pdcch_symbols": record.get("PdcchOccupiedSymbolNum"),
                "a3_offset_half_db": record.get("IntraFreqHoA3Offset [0.5dB]"),
                "neighbor_cells": record.get("PCell Neighbor Cell (gNodeBID_ARFCN_PCI)"),
            }
    if kpi is not None and not kpi.empty:
        numeric = [
            "gNodeB_ID",
            "Cell_ID",
            "Downlink PRB utilization(%)",
            "User Downlink Throughput(Mbps)",
            "Downlink Weak Coversge Ratio",
            "Downlink CCE Allocation Success Rate(%)",
        ]
        for column in numeric:
            if column in kpi.columns:
                kpi[column] = pd.to_numeric(kpi[column], errors="coerce")
        for _, record in kpi.iterrows():
            cell_key = make_cell_key(record.get("gNodeB_ID"), record.get("Cell_ID"))
            if not cell_key:
                continue
            profile = profiles.setdefault(cell_key, {})
            profile.update(
                {
                    "dl_prb": record.get("Downlink PRB utilization(%)"),
                    "user_dl_throughput": record.get("User Downlink Throughput(Mbps)"),
                    "weak_coverage_ratio": record.get("Downlink Weak Coversge Ratio"),
                    "dl_cce_success": record.get("Downlink CCE Allocation Success Rate(%)"),
                }
            )
    if mr is not None and not mr.empty:
        for column in [
            "Serving PCI",
            "Serving RSRP(dBm)",
            "Neighbor 1 PCI",
            "Neighbor 1 RSRP(dBm)",
            "Neighbor 2 PCI",
            "Neighbor 2 RSRP(dBm)",
            "Neighbor 3 PCI",
            "Neighbor 3 RSRP(dBm)",
            "Throughput(Mbps)",
        ]:
            if column in mr.columns:
                mr[column] = pd.to_numeric(mr[column], errors="coerce")
        if {"Serving PCI", "Serving RSRP(dBm)", "Throughput(Mbps)"}.issubset(mr.columns):
            grouped = mr.groupby("Serving PCI").agg(
                mr_samples=("Serving PCI", "size"),
                mr_avg_rsrp=("Serving RSRP(dBm)", "mean"),
                mr_avg_throughput=("Throughput(Mbps)", "mean"),
            )
            for pci, record in grouped.iterrows():
                cell_key = pci_to_cell.get(int(pci))
                if cell_key:
                    profiles.setdefault(cell_key, {}).update(round_record(record.to_dict()))
        if "Serving RSRP(dBm)" in mr.columns:
            for index in (1, 2, 3):
                pci_col = f"Neighbor {index} PCI"
                rsrp_col = f"Neighbor {index} RSRP(dBm)"
                if {pci_col, rsrp_col}.issubset(mr.columns):
                    mask = mr[rsrp_col] > mr["Serving RSRP(dBm)"] + 3
                    for pci, count in mr.loc[mask, pci_col].value_counts().items():
                        cell_key = pci_to_cell.get(int(pci))
                        if cell_key:
                            profile = profiles.setdefault(cell_key, {})
                            profile["stronger_neighbor_count"] = int(profile.get("stronger_neighbor_count", 0)) + int(count)
    return profiles


def option_profile(label: str, cell_profiles: dict[str, dict[str, Any]], config: pd.DataFrame | None) -> str:
    cells = re.findall(r"\b\d{6,8}_\d+\b", label)
    details = []
    for cell in cells:
        details.append(f"{cell}: {format_profile(cell_profiles.get(cell, {}))}")
    neighbor_match = re.search(r"Add neighbor relationship between (\d{6,8}_\d+) and (\d{6,8}_\d+)", label)
    if neighbor_match and config is not None:
        src, dst = neighbor_match.groups()
        details.append(f"neighbor_exists={neighbor_exists(config, src, dst)}")
    action = classify_action(label)
    if action:
        details.append(f"action={action}")
    return "; ".join(details) if details else "no direct cell match"


def format_profile(profile: dict[str, Any]) -> str:
    if not profile:
        return "no profile"
    keys = [
        "pci",
        "pdcch_symbols",
        "dl_cce_success",
        "dl_prb",
        "weak_coverage_ratio",
        "user_dl_throughput",
        "mr_samples",
        "mr_avg_rsrp",
        "mr_avg_throughput",
        "stronger_neighbor_count",
        "tx_power",
        "a3_offset_half_db",
    ]
    parts = []
    for key in keys:
        value = profile.get(key)
        if value is not None and not pd.isna(value):
            parts.append(f"{key}={round_value(value)}")
    return ", ".join(parts)


def neighbor_exists(config: pd.DataFrame, source_cell: str, target_cell: str) -> bool:
    target_profile = config.loc[config.apply(lambda record: make_cell_key(record.get("gNodeB ID"), record.get("Cell ID")) == target_cell, axis=1)]
    if target_profile.empty or "PCI" not in target_profile.columns:
        return False
    target_pci = str(int(pd.to_numeric(target_profile.iloc[0]["PCI"], errors="coerce")))
    source_profile = config.loc[config.apply(lambda record: make_cell_key(record.get("gNodeB ID"), record.get("Cell ID")) == source_cell, axis=1)]
    if source_profile.empty or "PCell Neighbor Cell (gNodeBID_ARFCN_PCI)" not in source_profile.columns:
        return False
    return target_pci in str(source_profile.iloc[0]["PCell Neighbor Cell (gNodeBID_ARFCN_PCI)"])


def classify_action(label: str) -> str:
    lowered = label.lower()
    if "pdcchoccupiedsymbolnum" in lowered:
        return "control_channel_symbols"
    if "a3 offset" in lowered:
        return "handover_offset"
    if "transmission power" in lowered:
        return "power"
    if "tilt angle" in lowered:
        return "tilt"
    if "azimuth" in lowered:
        return "azimuth"
    if "neighbor relationship" in lowered:
        return "neighbor_relation"
    if "test server" in lowered or "transmission issues" in lowered:
        return "external_transport"
    if "insufficient data" in lowered:
        return "insufficient_data"
    return ""


def make_cell_key(gnodeb: Any, cell_id: Any) -> str:
    if pd.isna(gnodeb) or pd.isna(cell_id):
        return ""
    return f"{int(gnodeb)}_{int(cell_id)}"


def round_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: round_value(value) for key, value in record.items()}


def round_value(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 3)
    return value


def summarize_mr(mr: pd.DataFrame) -> dict[str, Any]:
    numeric_columns = [
        "Serving PCI",
        "Serving RSRP(dBm)",
        "Neighbor 1 PCI",
        "Neighbor 1 RSRP(dBm)",
        "Neighbor 2 PCI",
        "Neighbor 2 RSRP(dBm)",
        "Neighbor 3 PCI",
        "Neighbor 3 RSRP(dBm)",
        "Throughput(Mbps)",
    ]
    for column in numeric_columns:
        if column in mr.columns:
            mr[column] = pd.to_numeric(mr[column], errors="coerce")
    summary: dict[str, Any] = {}
    if "Serving PCI" in mr.columns:
        summary["serving_distribution"] = mr["Serving PCI"].value_counts(dropna=True).to_dict()
    if {"Serving PCI", "Throughput(Mbps)", "Serving RSRP(dBm)"}.issubset(mr.columns):
        grouped = mr.groupby("Serving PCI").agg(
            samples=("Serving PCI", "size"),
            avg_throughput=("Throughput(Mbps)", "mean"),
            avg_serving_rsrp=("Serving RSRP(dBm)", "mean"),
        )
        summary["serving_stats"] = grouped.round(2).reset_index().to_dict(orient="records")
    stronger: dict[str, int] = {}
    if "Serving RSRP(dBm)" in mr.columns:
        for index in (1, 2, 3):
            pci_col = f"Neighbor {index} PCI"
            rsrp_col = f"Neighbor {index} RSRP(dBm)"
            if {pci_col, rsrp_col}.issubset(mr.columns):
                mask = mr[rsrp_col] > mr["Serving RSRP(dBm)"] + 3
                for pci, count in mr.loc[mask, pci_col].value_counts().items():
                    stronger[str(int(pci))] = stronger.get(str(int(pci)), 0) + int(count)
    summary["stronger_neighbor_counts"] = stronger
    return summary


def read_table(payload: Any, key: str) -> pd.DataFrame | None:
    if not isinstance(payload, dict) or key not in payload:
        return None
    text = payload.get(key)
    if not isinstance(text, str) or not text.strip():
        return None
    return pd.read_csv(StringIO(text), sep="|")


def append_track_a_trace(path: str | Path, result: TrackASolveResult) -> None:
    trace_path = Path(path)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result.__dict__, ensure_ascii=False) + "\n")
