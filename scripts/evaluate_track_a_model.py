from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telco_challenge.config import get_env, load_project_env
from telco_challenge.model_client import ChatClient


def extract_answer(text: str) -> str:
    boxed = re.findall(r"\\boxed\{([^{}]+)\}", text)
    if boxed:
        return clean_answer(boxed[-1])
    candidates = re.findall(r"\bC\d+(?:\|C\d+){0,3}\b", text)
    return clean_answer(candidates[-1]) if candidates else ""


def clean_answer(text: str) -> str:
    parts = re.findall(r"C\d+", text.upper())
    return "|".join(parts)


def iou(expected: str, actual: str) -> float:
    expected_set = set(expected.split("|"))
    actual_set = set(actual.split("|"))
    if not expected_set and not actual_set:
        return 1.0
    return len(expected_set & actual_set) / len(expected_set | actual_set)


def build_prompt(row: dict) -> str:
    options = "\n".join(f"{option['id']}: {option['label']}" for option in row["task"]["options"])
    return (
        f"{row['task']['description']}\n\n"
        f"Options:\n{options}\n\n"
        "Return only the final option label in the form \\boxed{C3} or \\boxed{C3|C5}."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/raw/Track A/data/Phase_1/train.json")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()

    load_project_env()
    client = ChatClient(
        base_url=get_env("QWEN_MODEL_BASE_URL", required=True),
        api_key=get_env("QWEN_MODEL_API_KEY", required=True),
        model_name=get_env("QWEN_MODEL_NAME", "qwen/qwen3.5-35b-a3b"),
    )

    rows = json.loads(Path(args.input).read_text(encoding="utf-8"))
    selected = rows[args.offset : args.offset + args.limit]
    scores = []
    for index, row in enumerate(selected, start=args.offset):
        prompt = build_prompt(row)
        response = client.complete([{"role": "user", "content": prompt}], temperature=0.0, max_tokens=256)
        prediction = extract_answer(response)
        score = iou(row["answer"], prediction)
        scores.append(score)
        print(f"{index}: expected={row['answer']} predicted={prediction or '<empty>'} iou={score:.3f}")
    print(f"Mean IOU: {sum(scores) / len(scores):.4f}")


if __name__ == "__main__":
    main()

