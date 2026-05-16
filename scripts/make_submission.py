from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telco_challenge.submission import apply_predictions, read_predictions, read_submission, validate_submission


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", default="data/reference/SampleSubmission.csv")
    parser.add_argument("--track-a")
    parser.add_argument("--track-b")
    parser.add_argument("--output", default="submissions/results.csv")
    args = parser.parse_args()

    df = read_submission(args.sample)

    if args.track_a:
        df = apply_predictions(df, read_predictions(args.track_a), "Track A")
    if args.track_b:
        df = apply_predictions(df, read_predictions(args.track_b), "Track B")

    issues = validate_submission(df)
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}", file=sys.stderr)
        raise SystemExit(1)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False, encoding="utf-8", lineterminator="\n")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()

