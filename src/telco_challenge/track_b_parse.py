from __future__ import annotations

import re
from dataclasses import dataclass

from telco_challenge.track_b import LocalTrackBOutputs


DEVICE_RE = re.compile(r"\b[A-Z][A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)+\b")
INTERFACE_RE = re.compile(r"\b(?:GE|GigabitEthernet|Ethernet|HundredGigE)\d+(?:/\d+)+\b")


@dataclass(frozen=True)
class LldpNeighbor:
    local_device: str
    local_interface: str
    neighbor_device: str
    neighbor_interface: str


def extract_known_devices(text: str, known_devices: list[str]) -> list[str]:
    ordered = sorted(known_devices, key=len, reverse=True)
    return [device for device in ordered if re.search(rf"(?<![A-Za-z0-9_-]){re.escape(device)}(?![A-Za-z0-9_-])", text)]


def infer_target_device(question: str, known_devices: list[str]) -> str | None:
    matches = extract_known_devices(question, known_devices)
    if not matches:
        return None
    positions = [(question.find(device), device) for device in matches]
    positions = [(pos, device) for pos, device in positions if pos >= 0]
    return min(positions)[1] if positions else matches[0]


def parse_lldp_neighbors(device: str, output: str) -> list[LldpNeighbor]:
    neighbors: list[LldpNeighbor] = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        if not INTERFACE_RE.fullmatch(parts[0]):
            continue
        if not parts[1].isdigit():
            continue
        if not INTERFACE_RE.fullmatch(parts[2]):
            continue
        neighbors.append(
            LldpNeighbor(
                local_device=device,
                local_interface=parts[0],
                neighbor_interface=parts[2],
                neighbor_device=parts[3],
            )
        )
    return neighbors


def up_interfaces(interface_brief_output: str) -> set[str]:
    interfaces: set[str] = set()
    for line in interface_brief_output.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        if INTERFACE_RE.fullmatch(parts[0]) and parts[1] == "up" and parts[2] == "up":
            interfaces.add(parts[0])
    return interfaces


def restore_links(question_number: int, question: str, outputs: LocalTrackBOutputs) -> list[str]:
    devices = outputs.devices(question_number)
    target = infer_target_device(question, devices)
    if target is None:
        return []

    links: dict[str, tuple[int, str]] = {}

    direct_lldp = outputs.execute(question_number, target, "display lldp neighbor brief")
    direct_up = up_interfaces(outputs.execute(question_number, target, "display interface brief").output)
    if direct_lldp.status_code == 200 and direct_lldp.output.strip():
        for item in parse_lldp_neighbors(target, direct_lldp.output):
            if direct_up and item.local_interface not in direct_up:
                continue
            line = f"{target}({item.local_interface})->{item.neighbor_device}({item.neighbor_interface})"
            links[item.local_interface] = (0, line)

    for device in devices:
        if device == target:
            continue
        result = outputs.execute(question_number, device, "display lldp neighbor brief")
        if result.status_code != 200 or not result.output.strip():
            continue
        for item in parse_lldp_neighbors(device, result.output):
            if item.neighbor_device != target:
                continue
            line = f"{target}({item.neighbor_interface})->{device}({item.local_interface})"
            links.setdefault(item.neighbor_interface, (1, line))

    return [value[1] for _, value in sorted(links.items(), key=lambda pair: _interface_sort_key(pair[0]))]


def _interface_sort_key(interface: str) -> tuple[int, ...]:
    numbers = [int(part) for part in re.findall(r"\d+", interface)]
    return tuple(numbers)

