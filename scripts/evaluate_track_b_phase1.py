from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telco_challenge.submission import read_predictions


def normalize_lines(value: str) -> list[str]:
    return [line.strip() for line in str(value).replace("\\n", "\n").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--ground-truth", default="data/raw/Track B/data/Phase_1/gt_phase1.csv")
    args = parser.parse_args()

    predictions = read_predictions(args.predictions).set_index("ID")["prediction"].to_dict()
    ground_truth = pd.read_csv(args.ground_truth, dtype=str, keep_default_na=False)

    total = 0
    exact = 0
    line_set = 0
    missing = []
    for _, row in ground_truth.iterrows():
        scenario_id = row["ID"]
        if scenario_id not in predictions:
            missing.append(scenario_id)
            continue
        total += 1
        expected = normalize_lines(row["Track B"])
        actual = normalize_lines(predictions[scenario_id])
        if actual == expected:
            exact += 1
        if set(actual) == set(expected):
            line_set += 1

    if missing:
        print(f"Missing predictions: {len(missing)}", file=sys.stderr)
    print(f"Compared: {total}")
    print(f"Exact order matches: {exact}")
    print(f"Line-set matches: {line_set}")
    if total:
        print(f"Exact order rate: {exact / total:.3f}")
        print(f"Line-set rate: {line_set / total:.3f}")


if __name__ == "__main__":
    main()

