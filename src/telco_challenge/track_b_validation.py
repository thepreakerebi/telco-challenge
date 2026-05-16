from __future__ import annotations

import re


ROUTING_REASONS = {
    "blackholeroute",
    "missingstaticroute",
    "staticrouteerror",
    "ARPconfigurationerror",
    "Layer3loop",
    "BGPconfigurationerror",
    "OSPFconfigurationerror",
    "loopbackinterfaceIPconfigurationconflict",
    "VXLANconfigurationerror",
    "L3VPNconfigurationerror",
    "L2VPNconfigurationerror",
    "ISISconfigurationerror",
    "SRV6-Policytunnelplanningerror",
    "NATexternalinterfaceattributeconfigurationerrororconfigurationmissing",
    "NATinternalinterfaceattributeconfigurationerrorormissing",
    "globalSTPnotenabled",
    "IPaddressprefixlistmissingcorrespondingusersourceIPAddress",
    "globalHRPhotredundancyprotocolnotenabled",
    "securitypolicyrulenotpermittingcorrespondingusers",
}

PORT_REASONS = {
    "shutdown",
    "interfaceIPerror",
    "trafficoccupyingportbandwidth",
    "MACaddressconfigurationerror",
    "VPNconfigurationmissing",
    "OSPFconfigurationerror",
    "MTUvalueconfigurationerror",
    "hostinformationcollectionfunctionmissing",
    "interfaceVLANconfigurationerror",
    "NATexternalinterfaceattributeconfigurationerrororconfigurationmissing",
    "NATinternalinterfaceattributeconfigurationerrorormissing",
    "portSTPnotenabled",
}


def validate_prediction(prediction: str) -> list[str]:
    issues: list[str] = []
    fault_line_count = 0
    for index, raw_line in enumerate(prediction.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if "->" in line:
            if not is_valid_path_line(line):
                issues.append(f"line {index}: invalid path format")
            continue
        parts = line.split(";")
        if len(parts) != 3:
            issues.append(f"line {index}: expected 3 semicolon-delimited fields")
            continue
        fault_line_count += 1
        reason = normalize_reason(parts[2])
        if looks_like_interface(parts[1]):
            if reason not in PORT_REASONS:
                issues.append(f"line {index}: unsupported port fault reason '{parts[2]}'")
        else:
            if reason not in ROUTING_REASONS:
                issues.append(f"line {index}: unsupported routing fault reason '{parts[2]}'")
    if fault_line_count > 8:
        issues.append(f"too many fault lines: {fault_line_count}; provide a minimal root-cause set")
    if not prediction.strip():
        issues.append("prediction is empty")
    return issues


def normalize_reason(reason: str) -> str:
    return re.sub(r"\s+", "", reason.strip())


def looks_like_interface(value: str) -> bool:
    return bool(re.search(r"\b(?:GE|GigabitEthernet|Ethernet|Eth-Trunk|Vlanif|HGE|HundredGigE)\d", value))


def is_valid_path_line(line: str) -> bool:
    return bool(re.match(r"^[A-Za-z0-9_-]+(?:_[A-Za-z0-9/.-]+)?(?:->[A-Za-z0-9_-]+(?:_[A-Za-z0-9/.-]+)?)+$", line))
