from __future__ import annotations

import re


def normalize_prediction(text: str) -> str:
    lines = [normalize_line(line) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def normalize_line(line: str) -> str:
    value = line.strip()
    value = re.sub(r"\s*->\s*", "->", value)
    value = re.sub(r"\s*;\s*", ";", value)
    value = re.sub(r"\s+", "", value)
    return value


def extract_track_b_answer(text: str) -> str:
    fenced = re.findall(r"```(?:text)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    candidates = fenced if fenced else [text]
    patterns = [
        r"^[A-Za-z0-9_-]+;[^;\n]+;[^;\n]+$",
        r"^[A-Za-z0-9_-]+(?:_[A-Za-z0-9/.-]+)?(?:->[A-Za-z0-9_-]+(?:_[A-Za-z0-9/.-]+)?)+$",
    ]
    for candidate in reversed(candidates):
        lines = []
        for raw_line in candidate.splitlines():
            line = normalize_line(raw_line)
            if any(re.match(pattern, line) for pattern in patterns):
                lines.append(line)
        if lines:
            return "\n".join(lines)
    return ""
