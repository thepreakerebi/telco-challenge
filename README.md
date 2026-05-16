# Telco Challenge

Python workspace for building, validating, and packaging submissions for the Telco Troubleshooting Agentic Challenge.

## Project Layout

```text
scripts/                 Command-line workflows
src/telco_challenge/     Reusable package code
docs/                    Notes and run details
data/reference/          Small reference files committed to git
data/raw/                Downloaded challenge data, ignored by git
data/processed/          Local derived data, ignored by git
predictions/             Per-track prediction files, ignored by git
traces/                  API and command traces, ignored by git
submissions/             Final CSV/ZIP outputs, ignored by git
```

## Setup

```bash
cd /Users/elvke/Documents/telco-challenge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Create a local environment file:

```bash
cp .env.example .env
```

Set the API and model values in `.env`. Keep this file private and untracked.

```bash
TRACK_A_SERVER_URL=https://124.71.227.61/no
TRACK_A_BEARER_TOKEN=

TRACK_B_SERVER_URL=https://124.71.227.61/ip/api/agent/execute
TRACK_B_BEARER_TOKEN=

QWEN_MODEL_BASE_URL=https://openrouter.ai/api/v1
QWEN_MODEL_NAME=qwen/qwen3.5-35b-a3b
QWEN_MODEL_API_KEY=
```

## Data

Download the dataset:

```bash
python scripts/download_data.py
```

Inspect the local files:

```bash
python scripts/inspect_data.py
```

## Readiness

Run the readiness check before live runs or submission packaging:

```bash
python scripts/check_readiness.py
```

This verifies local data, submission schema, encoding, and required credentials without printing secret values.

## Common Commands

Track A offline baseline:

```bash
python scripts/evaluate_track_a_baseline.py
python scripts/track_a_option_baseline.py --output predictions/track_a_option_baseline.csv
```

Track A API call:

```bash
python scripts/track_a_call.py tools

python scripts/solve_track_a.py \
  --limit 1 \
  --output predictions/track_a_live.csv
```

Track B local command lookup:

```bash
python scripts/track_b_local_index.py --question 1

python scripts/track_b_command.py \
  --source local \
  --question 1 \
  --device Gamma-Aegis-01 \
  --command "display interface brief"
```

Track B Phase 1 link baseline:

```bash
python scripts/track_b_restore_links.py \
  --questions 1,2,3,4,5,6 \
  --output predictions/phase1_link_baseline.csv

python scripts/evaluate_track_b_phase1.py \
  --predictions predictions/phase1_link_baseline.csv
```

Track B live solver:

```bash
python scripts/solve_track_b.py \
  --limit 1 \
  --output predictions/track_b_live.csv

python scripts/validate_track_b_predictions.py predictions/track_b_live.csv
```

Command outputs are cached under `outputs/track_b_command_cache/` by default.

## Build Submission

Per-track prediction files must use:

```csv
ID,prediction
...
```

Create and validate the final CSV:

```bash
python scripts/make_submission.py \
  --sample data/reference/SampleSubmission.csv \
  --track-a predictions/track_a.csv \
  --track-b predictions/track_b.csv \
  --output submissions/results.csv

python scripts/validate_submission.py submissions/results.csv
```

## Notes

Detailed challenge notes and current run constraints are in `docs/challenge-notes.md`.
