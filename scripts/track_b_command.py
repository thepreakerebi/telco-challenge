from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telco_challenge.config import DEFAULT_TRACK_B_URL, get_env, load_project_env
from telco_challenge.track_b import LocalTrackBOutputs, TrackBClient, append_trace


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", type=int, required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--source", choices=["cloud", "local"], default="cloud")
    parser.add_argument("--local-root", default="data/processed/track_b/devices_outputs")
    parser.add_argument("--trace", default="traces/track_b_commands.jsonl")
    args = parser.parse_args()

    load_project_env()
    if args.source == "cloud":
        token = get_env("TRACK_B_BEARER_TOKEN", required=True)
        endpoint_url = get_env("TRACK_B_SERVER_URL", DEFAULT_TRACK_B_URL)
        result = TrackBClient(endpoint_url=endpoint_url, token=token).execute(args.question, args.device, args.command)
    else:
        result = LocalTrackBOutputs(args.local_root).execute(args.question, args.device, args.command)

    append_trace(args.trace, result, source=args.source)
    if result.status_code >= 400:
        print(result.payload, file=sys.stderr)
        raise SystemExit(1)
    print(result.output)


if __name__ == "__main__":
    main()

