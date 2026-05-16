from __future__ import annotations

import argparse
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


def iou(expected: str, actual: str) -> float:
    expected_set = set(expected.split("|"))
    actual_set = set(actual.split("|"))
    if not expected_set and not actual_set:
        return 1.0
    return len(expected_set & actual_set) / len(expected_set | actual_set)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", default="data/raw/Track A/data/Phase_1/train.json")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--model", choices=["tfidf", "heuristic"], default="tfidf")
    args = parser.parse_args()

    rows = json.loads(Path(args.train).read_text(encoding="utf-8"))
    folds = max(2, args.folds)
    scores = []
    exact = 0
    for fold in range(folds):
        train = [row for index, row in enumerate(rows) if index % folds != fold]
        valid = [row for index, row in enumerate(rows) if index % folds == fold]
        model = build_model(args.model)
        model.fit(train)
        for row in valid:
            prediction = model.predict_row(row)
            score = iou(row["answer"], prediction)
            scores.append(score)
            exact += int(score == 1.0)

    print(f"Rows: {len(scores)}")
    print(f"Mean IOU: {sum(scores) / len(scores):.4f}")
    print(f"Exact match: {exact / len(scores):.4f}")


if __name__ == "__main__":
    main()
