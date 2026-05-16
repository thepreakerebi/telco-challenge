# Challenge Notes

## Data Sources

- Main dataset: https://huggingface.co/datasets/netop/Telco-Troubleshooting-Agentic-Challenge
- Phase 2 Track A data: https://huggingface.co/datasets/netop/Telco-Troubleshooting-Agentic-Challenge/tree/main/Track%20A/data/Phase_2
- Phase 2 Track B data: https://huggingface.co/datasets/netop/Telco-Troubleshooting-Agentic-Challenge/tree/main/Track%20B/data/Phase_2

## Rules And Constraints

- Use only challenge-provided datasets.
- Use open-source tools.
- Automated ML tools are not permitted.
- Base model is Qwen3.5-35B-A3B. Fine-tuning is allowed, replacing it with another architecture or different parameter scale is not.
- Code may be requested after close; keep the project reproducible.
- Phase 2 tokens are unique per team and track.
- Phase 2 allows 3 submissions.

## Submission Format

`result.csv` must contain:

- `ID`
- `Track A`
- `Track B`

Use the sample submission placeholders exactly for tracks not being competed.

Important: write CSV as UTF-8 without BOM. A Zindi discussion reports a zero score caused by a leading UTF-8 BOM marker.

