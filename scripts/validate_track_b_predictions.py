from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telco_challenge.submission import read_predictions
from telco_challenge.track_b_validation import validate_prediction


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("predictions")
    args = parser.parse_args()

    rows = read_predictions(args.predictions)
    failed = False
    for _, row in rows.iterrows():
        issues = validate_prediction(row["prediction"])
        if issues:
            failed = True
            print(f"{row['ID']}:")
            for issue in issues:
                print(f"  ERROR: {issue}")
    if failed:
        raise SystemExit(1)
    print(f"OK: {args.predictions} has {len(rows)} valid Track B predictions")


if __name__ == "__main__":
    main()
