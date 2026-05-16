from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telco_challenge.track_b import LocalTrackBOutputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="data/processed/track_b/devices_outputs")
    parser.add_argument("--question", type=int, required=True)
    parser.add_argument("--device")
    args = parser.parse_args()

    outputs = LocalTrackBOutputs(args.root)
    if args.device:
        for command in outputs.commands(args.question, args.device):
            print(command)
    else:
        for device in outputs.devices(args.question):
            print(device)


if __name__ == "__main__":
    main()

