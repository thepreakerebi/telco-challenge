# Telco Troubleshooting Agentic Challenge

Workspace for the Zindi Telco Troubleshooting Agentic Challenge. The repo is organized to keep data access, command traces, predictions, and final submissions reproducible while avoiding committed secrets or large challenge data files.

## Status

- Phase 2 closes on 19 May 2026.
- Track A: wireless troubleshooting. Answers are labels such as `C4` or pipe-separated labels such as `C3|C7`.
- Track B: IP network troubleshooting. Answers are open-ended device/interface/path/fault strings.
- Phase 2 uses dedicated cloud servers and bearer tokens per team and track.
- Submissions use one CSV with columns `ID`, `Track A`, `Track B`.
- Current blocker: Phase 2 Track A and Track B bearer tokens are required before running the live challenge APIs.

## Setup

```bash
cd /Users/elvke/Documents/telco-challenge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If the virtual environment is not active, most scripts still run with system Python, but installing the requirements is recommended before longer runs.

## Environment

Create `.env` from `.env.example` and keep it untracked:

```bash
cp .env.example .env
```

Recommended values:

```bash
TRACK_A_SERVER_URL=https://124.71.227.61/no
TRACK_A_BEARER_TOKEN=

TRACK_B_SERVER_URL=https://124.71.227.61/ip/api/agent/execute
TRACK_B_BEARER_TOKEN=

QWEN_MODEL_BASE_URL=https://openrouter.ai/api/v1
QWEN_MODEL_NAME=qwen/qwen3.5-35b-a3b
QWEN_MODEL_API_KEY=
```

Do not commit `.env`, prediction files, traces, or final submissions.

## Data

Download and inspect the challenge dataset:

```bash
python scripts/download_data.py
python scripts/inspect_data.py
```

Expected local layout after download:

```text
data/raw/
  Track A/
  Track B/
  submission/
data/reference/SampleSubmission.csv
```

`data/raw/` and `data/processed/` are ignored because they can contain large challenge artifacts.

## Readiness Check

Run this before live API calls or submission generation:

```bash
python scripts/check_readiness.py
```

The check verifies:

- Phase 2 Track A has 500 rows.
- Phase 2 Track B has 100 rows.
- `SampleSubmission.csv` has the required columns.
- The sample file has no UTF-8 BOM marker.
- Required tokens and model credentials are present.

Until the Zindi tokens are available, the expected missing values are:

```text
TRACK_A_BEARER_TOKEN
TRACK_B_BEARER_TOKEN
```

## Track A Utilities

Track A needs the challenge server because Phase 2 telemetry fields are placeholders in the downloaded JSON.

Examples:

```bash
python scripts/track_a_call.py tools

python scripts/track_a_call.py config_data \
  --scenario-id 40573780-92ac-4436-97c7-efca33b2a839
```

Named endpoints currently supported by the helper:

- `tools`
- `scenario`
- `all_scenarios`
- `config_data`
- `user_plane_data`
- `throughput_logs`
- `cell_info`
- `kpi_data`
- `mr_data`

## Track B Utilities

Track B Phase 2 also needs the live command API. Phase 1 includes local command outputs, which are useful for parser checks and regression tests.

Inspect available local devices for a Phase 1 question:

```bash
python scripts/track_b_local_index.py --question 1
```

Inspect command names for one device:

```bash
python scripts/track_b_local_index.py --question 1 --device Gamma-Aegis-01
```

Run one local command and write a trace:

```bash
python scripts/track_b_command.py \
  --source local \
  --question 1 \
  --device Gamma-Aegis-01 \
  --command "display interface brief"
```

Run one live command after `TRACK_B_BEARER_TOKEN` is set:

```bash
python scripts/track_b_command.py \
  --source cloud \
  --question 1 \
  --device Core_SW_01 \
  --command "display current-configuration"
```

Command traces are written to `traces/` and ignored by git.

## Phase 1 Track B Baseline

The link-restoration baseline parses LLDP and interface outputs for the public Phase 1 local files:

```bash
python scripts/track_b_restore_links.py \
  --questions 1,2,3,4,5,6 \
  --output predictions/phase1_link_baseline.csv

python scripts/evaluate_track_b_phase1.py \
  --predictions predictions/phase1_link_baseline.csv
```

Current check result on those six public link-restoration questions:

```text
Line-set matches: 6
Line-set rate: 1.000
```

## Submission Workflow

Generate or place predictions in `predictions/track_a.csv` and/or `predictions/track_b.csv`.

Expected per-track prediction format:

```csv
ID,prediction
...
```

Build a Zindi-compatible CSV:

```bash
python scripts/make_submission.py \
  --sample data/reference/SampleSubmission.csv \
  --track-a predictions/track_a.csv \
  --track-b predictions/track_b.csv \
  --output submissions/results.csv

python scripts/validate_submission.py submissions/results.csv
```

CSV files are written as UTF-8 without BOM.

For a one-track submission, keep the sample placeholder values exactly as provided for the other track. The merge script preserves placeholders unless a replacement prediction file is supplied for that track.

## Repository Hygiene

- Keep commits small and milestone-based.
- Keep secrets in `.env` only.
- Keep generated outputs in ignored folders: `predictions/`, `traces/`, `outputs/`, and `submissions/`.
- Use `scripts/check_readiness.py` before long runs and before final CSV creation.
