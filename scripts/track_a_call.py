from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telco_challenge.config import DEFAULT_TRACK_A_URL, get_env, load_project_env
from telco_challenge.track_a import TrackAClient


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("endpoint", help="Named endpoint such as tools, scenario, config_data, or a raw endpoint path")
    parser.add_argument("--scenario-id")
    parser.add_argument("--param", action="append", default=[], help="Query parameter as key=value")
    args = parser.parse_args()

    load_project_env()
    token = get_env("TRACK_A_BEARER_TOKEN", required=True)
    server_url = get_env("TRACK_A_SERVER_URL", DEFAULT_TRACK_A_URL)
    params = dict(item.split("=", 1) for item in args.param)

    client = TrackAClient(server_url=server_url, token=token)
    result = client.call(args.endpoint, scenario_id=args.scenario_id, params=params)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

