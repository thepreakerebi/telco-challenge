from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telco_challenge.submission import read_submission, validate_submission


def has_utf8_bom(path: Path) -> bool:
    with path.open("rb") as handle:
        return handle.read(3) == b"\xef\xbb\xbf"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("submission")
    args = parser.parse_args()

    path = Path(args.submission)
    if has_utf8_bom(path):
        print("ERROR: file starts with a UTF-8 BOM marker", file=sys.stderr)
        raise SystemExit(1)

    df = read_submission(path)
    issues = validate_submission(df)
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}", file=sys.stderr)
        raise SystemExit(1)

    print(f"OK: {path} has {len(df)} rows and valid columns")
    print(f"Track A non-empty: {df['Track A'].astype(bool).sum()}")
    print(f"Track B non-empty: {df['Track B'].astype(bool).sum()}")


if __name__ == "__main__":
    main()

