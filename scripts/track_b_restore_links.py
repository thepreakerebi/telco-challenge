from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telco_challenge.track_b import LocalTrackBOutputs
from telco_challenge.track_b_parse import restore_links


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/raw/Track B/data/Phase_1/test.json")
    parser.add_argument("--local-root", default="data/processed/track_b/devices_outputs")
    parser.add_argument("--questions", default="")
    parser.add_argument("--output", default="predictions/track_b_restore_links.csv")
    args = parser.parse_args()

    selected = {int(item) for item in args.questions.split(",") if item.strip()}
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    outputs = LocalTrackBOutputs(args.local_root)

    rows = []
    for item in data:
        question_number = int(item["task"]["id"])
        if selected and question_number not in selected:
            continue
        answer = "\n".join(restore_links(question_number, item["task"]["question"], outputs))
        rows.append({"ID": item["scenario_id"], "prediction": answer})

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ID", "prediction"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()

