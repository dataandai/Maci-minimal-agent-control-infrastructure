from __future__ import annotations

from pathlib import Path

REQUIRED_REDTEAM_ASSETS: tuple[str, ...] = (
    "evals/redteam/dataset_manifest.example.json",
    "evals/redteam/README.md",
    "evals/redteam/official_samples/prompt_injections_benchmark_sample.jsonl",
    "evals/redteam/official_samples/lakera_pint_sample.jsonl",
    "evals/redteam/official_samples/promptinject_sample.jsonl",
    "evals/redteam/official_samples/jailbreakbench_sample.jsonl",
    "evals/redteam/official_samples/harmbench_sample.jsonl",
    "evals/redteam/official_samples/bipia_indirect_prompt_injection_sample.jsonl",
    "evals/redteam/official_samples/rag_poisoned_docs_sample.jsonl",
    "evals/redteam/adapters/README.md",
    "evals/promptfoo/redteam.example.yaml",
    "evals/garak/README.md",
    "scripts/run_redteam_against_endpoint.py",
    "scripts/export_public_redteam_dataset.py",
    "scripts/verify_redteam_assets.py",
)


def missing_redteam_assets(repo_root: str | Path) -> tuple[str, ...]:
    root = Path(repo_root)
    return tuple(path for path in REQUIRED_REDTEAM_ASSETS if not (root / path).exists())
