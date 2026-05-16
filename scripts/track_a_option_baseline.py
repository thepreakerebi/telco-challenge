from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telco_challenge.track_a_baseline import TrackAOptionBaseline, TrackATfidfBaseline


def build_model(name: str):
    if name == "tfidf":
        return TrackATfidfBaseline()
    if name == "heuristic":
        return TrackAOptionBaseline()
    raise ValueError(f"Unsupported model: {name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", default="data/raw/Track A/data/Phase_1/train.json")
    parser.add_argument("--input", default="data/raw/Track A/data/Phase_2/test.json")
    parser.add_argument("--output", default="predictions/track_a_option_baseline.csv")
    parser.add_argument("--model", choices=["tfidf", "heuristic"], default="tfidf")
    args = parser.parse_args()

    train = json.loads(Path(args.train).read_text(encoding="utf-8"))
    rows = json.loads(Path(args.input).read_text(encoding="utf-8"))
    model = build_model(args.model)
    model.fit(train)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ID", "prediction"], lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({"ID": row["scenario_id"], "prediction": model.predict_row(row)})
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
