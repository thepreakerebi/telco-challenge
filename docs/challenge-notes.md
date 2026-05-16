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

## Local Status

- Live Phase 2 API calls require `TRACK_A_BEARER_TOKEN` and `TRACK_B_BEARER_TOKEN`.
- The OpenRouter-compatible Qwen endpoint is configured through `QWEN_MODEL_BASE_URL`, `QWEN_MODEL_NAME`, and `QWEN_MODEL_API_KEY`.
- Track A downloaded Phase 2 telemetry fields are placeholders; competitive answers need live telemetry.
- Track B Phase 2 command outputs are served by the live API; public local outputs cover Phase 1 only.

## Baseline Notes

- Track A option-text baselines validate at roughly `0.117` mean IOU on public Phase 1 cross-validation.
- Qwen option-only evaluation is useful for provider validation, but option-only prompts are not competitive without telemetry context.
- Track B Phase 1 link-restoration baseline reaches full line-set match on the six public link-restoration checks.
