from __future__ import annotations

from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = ["ID", "Track A", "Track B"]


def read_submission(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    return df[REQUIRED_COLUMNS].copy()


def read_predictions(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    if "ID" not in df.columns:
        raise ValueError(f"{path} is missing ID column")
    if "prediction" not in df.columns:
        raise ValueError(f"{path} is missing prediction column")
    if df["ID"].duplicated().any():
        duplicated = df.loc[df["ID"].duplicated(), "ID"].head(5).tolist()
        raise ValueError(f"{path} contains duplicate IDs, examples: {duplicated}")
    return df[["ID", "prediction"]].copy()


def apply_predictions(
    sample: pd.DataFrame,
    predictions: pd.DataFrame,
    target_column: str,
) -> pd.DataFrame:
    if target_column not in {"Track A", "Track B"}:
        raise ValueError(f"Unsupported target column: {target_column}")

    unknown = sorted(set(predictions["ID"]) - set(sample["ID"]))
    if unknown:
        raise ValueError(f"{target_column} predictions contain IDs absent from sample, first: {unknown[:5]}")

    result = sample.copy()
    mapped = predictions.set_index("ID")["prediction"]
    mask = result["ID"].isin(mapped.index)
    result.loc[mask, target_column] = result.loc[mask, "ID"].map(mapped)
    return result


def validate_submission(df: pd.DataFrame) -> list[str]:
    issues: list[str] = []
    if list(df.columns) != REQUIRED_COLUMNS:
        issues.append(f"Columns must be exactly {REQUIRED_COLUMNS}; got {list(df.columns)}")
    if df["ID"].duplicated().any():
        issues.append("Submission contains duplicate IDs")
    empty_rows = (df["Track A"].eq("") & df["Track B"].eq("")).sum()
    if empty_rows:
        issues.append(f"{empty_rows} rows have both Track A and Track B empty")
    return issues

