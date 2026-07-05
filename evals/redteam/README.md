# Red-Team Evaluation Assets

This directory contains the red-team dataset manifest and local JSONL export files used by the Maci red-team harness.

## Required files

```text
evals/redteam/dataset_manifest.example.json
evals/redteam/official_samples/prompt_injections_benchmark_sample.jsonl
evals/redteam/official_samples/lakera_pint_sample.jsonl
evals/redteam/official_samples/promptinject_sample.jsonl
evals/redteam/official_samples/jailbreakbench_sample.jsonl
evals/redteam/official_samples/harmbench_sample.jsonl
evals/redteam/official_samples/bipia_indirect_prompt_injection_sample.jsonl
evals/redteam/official_samples/rag_poisoned_docs_sample.jsonl
```

The sample rows in this repository are intentionally small and safe. They validate the schema, loader, guardrail boundary, live HTTP runner, and packaging. For real evaluation, export permitted rows from upstream public datasets into the same JSONL schema and point the manifest to those files.

## Verify assets

```bash
python scripts/verify_redteam_assets.py
```

## Offline CI run

```bash
pytest -q tests/red_team/
```

## Live dev/staging run

```bash
export MACI_REDTEAM_JWT="<test-tenant-jwt>"
python scripts/run_redteam_against_endpoint.py \
  --endpoint "https://<dev-api>/agent" \
  --manifest evals/redteam/dataset_manifest.example.json \
  --output redteam-live-report.json
```

## Export real public datasets

Use `scripts/export_public_redteam_dataset.py` to convert a Hugging Face dataset, local JSONL, local JSON, local CSV, or URL-downloaded JSONL into Maci's normalized JSONL.

Examples:

```bash
# Hugging Face dataset export, requires: pip install -e '.[evals]'
python scripts/export_public_redteam_dataset.py \
  --source hf \
  --hf-dataset JailbreakBench/JBB-Behaviors \
  --split train \
  --text-field behavior \
  --dataset-name jailbreakbench \
  --output evals/redteam/exports/jailbreakbench_export.jsonl \
  --max-cases 100

# Local CSV/JSONL export
python scripts/export_public_redteam_dataset.py \
  --source local \
  --input downloaded_dataset.jsonl \
  --text-field prompt \
  --label-field label \
  --dataset-name prompt_injections_benchmark \
  --output evals/redteam/exports/prompt_injections_export.jsonl
```

Do not run live red-team datasets against production tenants or production data.
