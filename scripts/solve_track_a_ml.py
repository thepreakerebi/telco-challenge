"""
Feature-based Track A solver — no LLM required.

Pipeline:
1. Extract features from Phase 1 training data (embedded network data)
2. Pre-fetch Phase 2 test data from the Track A server API
3. Train a gradient-boosted classifier on (option features) -> is_correct
4. Predict Phase 2 answers
"""
from __future__ import annotations

import csv
import json
import re
import sys
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telco_challenge.config import DEFAULT_TRACK_A_URL, get_env, load_project_env
from telco_challenge.track_a import TrackAClient
from telco_challenge.track_a_solver import (
    build_cell_profiles,
    classify_action,
    make_cell_key,
    neighbor_exists,
)

ENDPOINTS = ["throughput_logs", "config_data", "kpi_data", "mr_data"]

ACTION_TYPES = [
    "add_neighbor",
    "decrease_power",
    "increase_power",
    "tilt_down",
    "tilt_up",
    "azimuth",
    "increase_a3",
    "decrease_a3",
    "pdcch",
    "external_transport",
    "insufficient_data",
    "none",
]

ACTION_MAP = {
    "neighbor_relation": "add_neighbor",
    "power": "power",
    "press_tilt": "tilt_down",
    "lift_tilt": "tilt_up",
    "azimuth": "azimuth",
    "increase_a3": "increase_a3",
    "decrease_a3": "decrease_a3",
    "control_channel_symbols": "pdcch",
    "test_server": "external_transport",
    "insufficient_data": "insufficient_data",
    "handover_offset": "handover_offset",
}

N_ACTION_FEATURES = len(ACTION_TYPES) + 2  # +2 for power_up/power_down split and handover
CELL_METRIC_KEYS = [
    "dl_prb",
    "user_dl_throughput",
    "weak_coverage_ratio",
    "dl_cce_success",
    "mr_avg_rsrp",
    "mr_avg_throughput",
    "stronger_neighbor_count",
    "tx_power",
    "a3_offset_half_db",
    "pdcch_symbols",
    "mr_samples",
]
N_CELL_FEATURES = len(CELL_METRIC_KEYS) * 2  # mean + max across mentioned cells


def extract_cells(label: str) -> list[str]:
    return re.findall(r"\b\d{6,8}_\d+\b", label)


def action_onehot(action_raw: str, label: str) -> list[float]:
    mapped = ACTION_MAP.get(action_raw, action_raw or "none")
    # Split "power" into increase/decrease based on label
    if mapped == "power":
        if "decrease" in label.lower():
            mapped = "decrease_power"
        else:
            mapped = "increase_power"
    vec = [0.0] * len(ACTION_TYPES)
    if mapped in ACTION_TYPES:
        vec[ACTION_TYPES.index(mapped)] = 1.0
    return vec


def cell_features(cells: list[str], profiles: dict[str, dict]) -> list[float]:
    if not cells:
        return [0.0] * N_CELL_FEATURES
    rows = [profiles.get(c, {}) for c in cells]
    means, maxs = [], []
    for key in CELL_METRIC_KEYS:
        vals = [r[key] for r in rows if isinstance(r.get(key), (int, float)) and not np.isnan(r.get(key, float("nan")))]
        means.append(float(np.mean(vals)) if vals else 0.0)
        maxs.append(float(np.max(vals)) if vals else 0.0)
    return means + maxs


def scenario_stats(profiles: dict[str, dict]) -> dict[str, float]:
    if not profiles:
        return {}
    stats: dict[str, list[float]] = {}
    for profile in profiles.values():
        for key in CELL_METRIC_KEYS:
            val = profile.get(key)
            if isinstance(val, (int, float)) and not np.isnan(val):
                stats.setdefault(key, []).append(float(val))
    return {k: float(np.mean(v)) for k, v in stats.items() if v}


def relative_features(cells: list[str], profiles: dict[str, dict], s_stats: dict[str, float]) -> list[float]:
    """Cell metrics relative to scenario average."""
    if not cells or not s_stats:
        return [0.0] * len(CELL_METRIC_KEYS)
    rows = [profiles.get(c, {}) for c in cells]
    rel = []
    for key in CELL_METRIC_KEYS:
        avg = s_stats.get(key, 0.0)
        vals = [r[key] for r in rows if isinstance(r.get(key), (int, float)) and not np.isnan(r.get(key, float("nan")))]
        if vals and avg != 0:
            rel.append(float(np.mean(vals)) / avg - 1.0)
        else:
            rel.append(0.0)
    return rel


def build_feature_vector(
    option: dict,
    profiles: dict[str, dict],
    s_stats: dict[str, float],
    config_df: pd.DataFrame | None,
    tag: str,
) -> list[float]:
    label = option["label"]
    action_raw = classify_action(label)
    cells = extract_cells(label)

    feats: list[float] = []
    feats += action_onehot(action_raw, label)
    feats += cell_features(cells, profiles)
    feats += relative_features(cells, profiles, s_stats)
    feats.append(1.0 if tag == "multiple-answer" else 0.0)
    feats.append(float(len(cells)))

    # Neighbor existence feature
    neighbor_match = re.search(r"Add neighbor relationship between (\d{6,8}_\d+) and (\d{6,8}_\d+)", label)
    if neighbor_match and config_df is not None:
        src, dst = neighbor_match.groups()
        feats.append(1.0 if neighbor_exists(config_df, src, dst) else 0.0)
    else:
        feats.append(0.0)

    return feats


def parse_embedded_data(row: dict) -> tuple:
    d = row.get("data", {})

    def read(key: str) -> pd.DataFrame | None:
        val = d.get(key, "")
        if not isinstance(val, str) or not val.strip() or "API" in val:
            return None
        try:
            return pd.read_csv(StringIO(val), sep="|")
        except Exception:
            return None

    config = read("network_configuration_data")
    kpi = read("traffic_data")
    mr = read("mr_data")
    throughput = read("user_plane_data")
    return config, kpi, mr, throughput


def parse_api_data(evidence: dict) -> tuple:
    def read_api(payload: Any, key: str) -> pd.DataFrame | None:
        if not isinstance(payload, dict) or key not in payload:
            return None
        text = payload.get(key)
        if not isinstance(text, str) or not text.strip():
            return None
        try:
            return pd.read_csv(StringIO(text), sep="|")
        except Exception:
            return None

    config = read_api(evidence.get("config_data", {}), "Network Configuration Data")
    kpi = read_api(evidence.get("kpi_data", {}), "Traffic Data")
    mr = read_api(evidence.get("mr_data", {}), "MR Data")
    throughput = read_api(evidence.get("throughput_logs", {}), "Logs")
    return config, kpi, mr, throughput


def build_dataset(rows: list[dict], use_embedded: bool = True, api_client: TrackAClient | None = None):
    X, y, groups = [], [], []
    for i, row in enumerate(rows):
        sid = row["scenario_id"]
        tag = row.get("tag", "single-answer")
        answer_ids = set(str(row.get("answer", "")).split("|")) if row.get("answer") and row["answer"] != "To be determined" else None

        if use_embedded:
            config, kpi, mr, _ = parse_embedded_data(row)
        else:
            assert api_client is not None
            evidence = {ep: api_client.call(ep, scenario_id=sid) for ep in ENDPOINTS}
            config, kpi, mr, _ = parse_api_data(evidence)

        profiles = build_cell_profiles(config, kpi, mr)
        s_stats = scenario_stats(profiles)

        for opt in row["task"]["options"]:
            feats = build_feature_vector(opt, profiles, s_stats, config, tag)
            X.append(feats)
            if answer_ids is not None:
                y.append(1 if opt["id"] in answer_ids else 0)
            groups.append(sid)

        if (i + 1) % 50 == 0:
            print(f"  processed {i + 1}/{len(rows)}")

    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32) if y else None, groups


# Action prior: P(correct | action type) from Phase 1 training analysis
ACTION_PRIOR = {
    "insufficient_data": 0.126,
    "external_transport": 0.119,
    "none": 0.061,
    "neighbor_relation": 0.060,
    "control_channel_symbols": 0.060,
    "tilt_down": 0.051,
    "tilt_up": 0.051,
    "handover_offset": 0.047,
    "decrease_power": 0.037,
    "increase_power": 0.037,
    "azimuth": 0.035,
    "increase_a3": 0.030,
    "decrease_a3": 0.030,
    "add_neighbor": 0.060,
    "pdcch": 0.060,
}
PRIOR_WEIGHT = 0.25  # blend: 75% model score + 25% prior


def predict_scenario(row: dict, classifier, profiles: dict, s_stats: dict, config_df) -> str:
    tag = row.get("tag", "single-answer")
    options = row["task"]["options"]
    scores = []
    for opt in options:
        feats = build_feature_vector(opt, profiles, s_stats, config_df, tag)
        model_prob = classifier.predict_proba([feats])[0][1]
        # Blend with action-type prior to avoid systematic under/over-prediction
        action_raw = classify_action(opt["label"])
        label = opt["label"]
        mapped = ACTION_MAP.get(action_raw, action_raw or "none")
        if mapped == "power":
            mapped = "decrease_power" if "decrease" in label.lower() else "increase_power"
        prior = ACTION_PRIOR.get(mapped, 0.04)
        blended = (1 - PRIOR_WEIGHT) * model_prob + PRIOR_WEIGHT * prior
        scores.append((opt["id"], blended, model_prob))
    scores.sort(key=lambda x: -x[1])

    if tag == "single-answer":
        return scores[0][0]
    else:
        # Training data: multi-answer questions have ONLY 2 or 4 answers, never 3.
        # Use score gap between positions 2-3 to decide.
        s1 = scores[0][1]
        s2 = scores[1][1] if len(scores) > 1 else 0
        s3 = scores[2][1] if len(scores) > 2 else 0
        s4 = scores[3][1] if len(scores) > 3 else 0

        # If there's a sharp drop after position 2, predict 2; otherwise predict 4
        gap_2_3 = s2 - s3  # gap between 2nd and 3rd
        gap_3_4 = s3 - s4  # gap between 3rd and 4th
        # Predict 4 when 3rd score is still substantial relative to 2nd
        if s2 > 0 and s3 / s2 > 0.65 and s4 / s2 > 0.40:
            top_n = 4
        else:
            top_n = 2
        selected = [oid for oid, _, _ in scores[:top_n]]
        selected.sort(key=lambda x: int(re.search(r"\d+", x).group()))
        return "|".join(selected)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--train", default="data/raw/Track A/data/Phase_1/train.json")
    parser.add_argument("--test", default="data/raw/Track A/data/Phase_2/test.json")
    parser.add_argument("--output", default="predictions/track_a_ml_phase2.csv")
    parser.add_argument("--cache-dir", default="outputs/track_a_api_cache")
    parser.add_argument("--fetch-only", action="store_true", help="Only pre-fetch API data, don't predict")
    parser.add_argument("--resume", action="store_true", help="Skip already-predicted scenarios")
    args = parser.parse_args()

    load_project_env()
    api_client = TrackAClient(
        server_url=get_env("TRACK_A_SERVER_URL", DEFAULT_TRACK_A_URL),
        token=get_env("TRACK_A_BEARER_TOKEN", required=True),
        timeout=45.0,
        cache_dir=args.cache_dir,
    )

    train_rows = json.loads(Path(args.train).read_text(encoding="utf-8"))
    test_rows = json.loads(Path(args.test).read_text(encoding="utf-8"))

    # Step 1: Build training features from embedded data
    print(f"Building training features from {len(train_rows)} examples...")
    X_train, y_train, _ = build_dataset(train_rows, use_embedded=True)
    print(f"Training matrix: {X_train.shape}, positives: {y_train.sum()}/{len(y_train)}")

    # Step 2: Train classifier
    print("Training classifier...")
    try:
        from sklearn.ensemble import GradientBoostingClassifier
        clf = GradientBoostingClassifier(n_estimators=200, max_depth=4, learning_rate=0.1, subsample=0.8, random_state=42)
    except ImportError:
        from sklearn.ensemble import RandomForestClassifier
        clf = RandomForestClassifier(n_estimators=300, max_depth=8, class_weight="balanced", random_state=42, n_jobs=-1)
    clf.fit(X_train, y_train)
    train_pred = clf.predict(X_train)
    print(f"Train accuracy: {(train_pred == y_train).mean():.4f}")

    if args.fetch_only:
        print("Pre-fetching Phase 2 API data...")
        for i, row in enumerate(test_rows):
            sid = row["scenario_id"]
            for ep in ENDPOINTS:
                api_client.call(ep, scenario_id=sid)
            if (i + 1) % 25 == 0:
                print(f"  fetched {i + 1}/{len(test_rows)}")
        print("Done pre-fetching.")
        return

    # Step 3: Predict Phase 2
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Load already-completed predictions for resume
    completed: dict[str, str] = {}
    if args.resume and output.exists():
        with output.open("r", encoding="utf-8", newline="") as fh:
            for row_r in csv.DictReader(fh):
                if row_r.get("prediction"):
                    completed[row_r["ID"]] = row_r["prediction"]
        print(f"Resuming: {len(completed)} already done, {len(test_rows) - len(completed)} remaining")

    remaining = [r for r in test_rows if r["scenario_id"] not in completed]
    print(f"Predicting {len(remaining)} Phase 2 scenarios...")

    mode = "a" if args.resume and completed else "w"
    with output.open(mode, encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["ID", "prediction"], lineterminator="\n")
        if mode == "w":
            writer.writeheader()
        for i, row in enumerate(remaining):
            sid = row["scenario_id"]
            # Retry up to 3 times on connection errors
            for attempt in range(3):
                try:
                    evidence = {ep: api_client.call(ep, scenario_id=sid) for ep in ENDPOINTS}
                    break
                except Exception as exc:
                    if attempt == 2:
                        raise
                    import time; time.sleep(2 ** attempt)
            config, kpi, mr, _ = parse_api_data(evidence)
            profiles = build_cell_profiles(config, kpi, mr)
            s_stats = scenario_stats(profiles)
            prediction = predict_scenario(row, clf, profiles, s_stats, config)
            writer.writerow({"ID": sid, "prediction": prediction})
            fh.flush()
            if (i + 1) % 25 == 0:
                print(f"  predicted {i + 1}/{len(remaining)}: last={prediction}")

    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
