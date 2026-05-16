from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telco_challenge.config import DEFAULT_TRACK_A_URL, DEFAULT_TRACK_B_URL, get_env, load_project_env
from telco_challenge.submission import read_submission, validate_submission


REQUIRED_FILES = [
    Path("data/reference/SampleSubmission.csv"),
    Path("data/raw/Track A/data/Phase_2/test.json"),
    Path("data/raw/Track B/data/Phase_2/test.json"),
]


def has_bom(path: Path) -> bool:
    return path.read_bytes().startswith(b"\xef\xbb\xbf")


def check_file(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, f"missing: {path}"
    return True, f"found: {path}"


def check_phase_count(path: Path, expected: int) -> tuple[bool, str]:
    if not path.exists():
        return False, f"cannot count missing file: {path}"
    data = json.loads(path.read_text(encoding="utf-8"))
    actual = len(data)
    if actual != expected:
        return False, f"{path} has {actual} rows; expected {expected}"
    return True, f"{path} has {actual} rows"


def check_env(name: str, default: str | None = None) -> tuple[bool, str]:
    value = get_env(name, default)
    if not value:
        return False, f"{name} is not set"
    if default and name not in os.environ:
        return True, f"{name} uses default"
    return True, f"{name} is set"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    args = parser.parse_args()

    load_project_env(args.env)

    checks: list[tuple[bool, str]] = []
    checks.extend(check_file(path) for path in REQUIRED_FILES)
    checks.append(check_phase_count(Path("data/raw/Track A/data/Phase_2/test.json"), 500))
    checks.append(check_phase_count(Path("data/raw/Track B/data/Phase_2/test.json"), 100))

    sample_path = Path("data/reference/SampleSubmission.csv")
    if sample_path.exists():
        checks.append((not has_bom(sample_path), "sample submission has no BOM" if not has_bom(sample_path) else "sample submission has a BOM"))
        issues = validate_submission(read_submission(sample_path))
        checks.append((not issues, "sample submission schema is valid" if not issues else "; ".join(issues)))

    checks.append(check_env("TRACK_A_SERVER_URL", DEFAULT_TRACK_A_URL))
    checks.append(check_env("TRACK_A_BEARER_TOKEN"))
    checks.append(check_env("TRACK_B_SERVER_URL", DEFAULT_TRACK_B_URL))
    checks.append(check_env("TRACK_B_BEARER_TOKEN"))
    checks.append(check_env("QWEN_MODEL_BASE_URL"))
    checks.append(check_env("QWEN_MODEL_NAME", "qwen/qwen3.5-35b-a3b"))
    checks.append(check_env("QWEN_MODEL_API_KEY"))

    failed = False
    for ok, message in checks:
        label = "OK" if ok else "NEEDS"
        print(f"{label}: {message}")
        failed = failed or not ok

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
