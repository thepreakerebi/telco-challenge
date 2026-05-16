# Telco Troubleshooting Agentic Challenge

Workspace for the Zindi Telco Troubleshooting Agentic Challenge.

## Current Phase

- Phase 2 closes on 19 May 2026.
- Track A: wireless troubleshooting. Answers are labels such as `C4` or pipe-separated labels such as `C3|C7`.
- Track B: IP network troubleshooting. Answers are open-ended device/interface/path/fault strings.
- Phase 2 uses dedicated cloud servers and bearer tokens per team and track.
- Submissions use one CSV with columns `ID`, `Track A`, `Track B`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Download Data

```bash
python scripts/download_data.py
python scripts/inspect_data.py
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
