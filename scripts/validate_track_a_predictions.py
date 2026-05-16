from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telco_challenge.submission import read_predictions
from telco_challenge.track_a_validation import validate_track_a_prediction


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("predictions")
    parser.add_argument("--input", default="data/raw/Track A/data/Phase_2/test.json")
    args = parser.parse_args()

    rows = {row["scenario_id"]: row for row in json.loads(Path(args.input).read_text(encoding="utf-8"))}
    predictions = read_predictions(args.predictions)
    failed = False
    for _, prediction_row in predictions.iterrows():
        row = rows.get(prediction_row["ID"])
        if row is None:
            failed = True
            print(f"{prediction_row['ID']}:")
            print("  ERROR: unknown ID")
            continue
        issues = validate_track_a_prediction(prediction_row["prediction"], row)
        if issues:
            failed = True
            print(f"{prediction_row['ID']}:")
            for issue in issues:
                print(f"  ERROR: {issue}")
    if failed:
        raise SystemExit(1)
    print(f"OK: {args.predictions} has {len(predictions)} valid Track A predictions")


if __name__ == "__main__":
    main()
