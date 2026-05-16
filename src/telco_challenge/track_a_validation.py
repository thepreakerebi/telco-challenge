from __future__ import annotations

import re


def validate_track_a_prediction(prediction: str, row: dict) -> list[str]:
    issues: list[str] = []
    allowed = {option["id"] for option in row["task"]["options"]}
    labels = re.findall(r"C\d+", prediction)
    if not labels:
        return ["prediction is empty"]
    unknown = [label for label in labels if label not in allowed]
    if unknown:
        issues.append(f"unknown labels: {unknown}")
    if "|".join(labels) != prediction:
        issues.append("prediction must contain only C-labels separated by |")
    if row.get("tag") == "multiple-answer":
        if not 2 <= len(labels) <= 4:
            issues.append("multiple-answer rows require two to four labels")
    elif len(labels) != 1:
        issues.append("single-answer rows require exactly one label")
    if len(set(labels)) != len(labels):
        issues.append("duplicate labels")
    return issues
