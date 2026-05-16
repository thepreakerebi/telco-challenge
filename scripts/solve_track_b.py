from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telco_challenge.config import DEFAULT_TRACK_B_URL, get_env, load_project_env
from telco_challenge.model_client import ChatClient
from telco_challenge.track_b import TrackBClient
from telco_challenge.track_b_solver import TrackBSolver, append_solve_trace


def load_completed(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {row["ID"] for row in csv.DictReader(handle) if row.get("prediction")}


def append_prediction(path: Path, scenario_id: str, prediction: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ID", "prediction"], lineterminator="\n")
        if not exists:
            writer.writeheader()
        writer.writerow({"ID": scenario_id, "prediction": prediction})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/raw/Track B/data/Phase_2/test.json")
    parser.add_argument("--output", default="predictions/track_b_live.csv")
    parser.add_argument("--command-trace", default="traces/track_b_commands.jsonl")
    parser.add_argument("--solve-trace", default="traces/track_b_solutions.jsonl")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    load_project_env()
    command_client = TrackBClient(
        endpoint_url=get_env("TRACK_B_SERVER_URL", DEFAULT_TRACK_B_URL),
        token=get_env("TRACK_B_BEARER_TOKEN", required=True),
        timeout=45.0,
    )
    model_client = ChatClient(
        base_url=get_env("QWEN_MODEL_BASE_URL", required=True),
        api_key=get_env("QWEN_MODEL_API_KEY", required=True),
        model_name=get_env("QWEN_MODEL_NAME", "qwen/qwen3.5-35b-a3b"),
        timeout=180.0,
    )
    solver = TrackBSolver(command_client, model_client, args.command_trace)

    rows = json.loads(Path(args.input).read_text(encoding="utf-8"))
    rows = rows[args.offset :]
    if args.limit is not None:
        rows = rows[: args.limit]

    output = Path(args.output)
    completed = load_completed(output) if args.resume else set()
    for row in rows:
        if row["scenario_id"] in completed:
            continue
        result = solver.solve(row)
        append_prediction(output, result.scenario_id, result.prediction)
        append_solve_trace(args.solve_trace, result)
        print(f"{result.question_number}: commands={result.command_count} prediction_lines={len(result.prediction.splitlines())}")


if __name__ == "__main__":
    main()

