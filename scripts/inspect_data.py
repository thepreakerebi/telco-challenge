from __future__ import annotations

import json
from pathlib import Path


def summarize_json(path: Path) -> None:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, list):
        print(f"{path}: list[{len(data)}]")
        if data:
            first = data[0]
            if isinstance(first, dict):
                print(f"  keys: {sorted(first.keys())}")
                print(f"  first: {json.dumps(first, ensure_ascii=False)[:500]}")
    elif isinstance(data, dict):
        print(f"{path}: dict keys={sorted(data.keys())}")
        print(f"  preview: {json.dumps(data, ensure_ascii=False)[:500]}")
    else:
        print(f"{path}: {type(data).__name__}")


def main() -> None:
    root = Path("data/raw")
    if not root.exists():
        raise SystemExit("data/raw does not exist. Run scripts/download_data.py first.")
    for path in sorted(root.rglob("*.json")):
        summarize_json(path)


if __name__ == "__main__":
    main()

