from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from maci.redteam import OfficialDatasetName, RedTeamChannel, RedTeamDatasetLoader
from maci.redteam_assets import REQUIRED_REDTEAM_ASSETS, missing_redteam_assets

ROOT = Path(__file__).resolve().parents[2]


def test_required_redteam_assets_are_packaged() -> None:
    missing = missing_redteam_assets(ROOT)
    assert not missing, f"Missing red-team assets: {missing}"
    assert len(REQUIRED_REDTEAM_ASSETS) >= 14


def test_manifest_references_existing_non_empty_jsonl_files() -> None:
    manifest_path = ROOT / "evals/redteam/dataset_manifest.example.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    for dataset in data["datasets"]:
        path = manifest_path.parent / dataset["path"]
        assert path.exists(), f"Missing manifest dataset path: {path}"
        assert path.stat().st_size > 50, f"Dataset sample is unexpectedly empty: {path}"


def test_manifest_loads_all_required_dataset_families_and_channels() -> None:
    cases = RedTeamDatasetLoader().load_manifests_file(ROOT / "evals/redteam/dataset_manifest.example.json")
    datasets = {case.source_dataset for case in cases}
    channels = {case.channel for case in cases}
    assert len(cases) >= 16
    assert OfficialDatasetName.PROMPT_INJECTIONS_BENCHMARK in datasets
    assert OfficialDatasetName.LAKERA_PINT in datasets
    assert OfficialDatasetName.PROMPTINJECT in datasets
    assert OfficialDatasetName.JAILBREAKBENCH in datasets
    assert OfficialDatasetName.HARMBENCH in datasets
    assert RedTeamChannel.RETRIEVED_CONTEXT in channels
    assert RedTeamChannel.TOOL_OUTPUT in channels
    assert any(case.expected_action == "allow" for case in cases)


def test_verify_redteam_assets_script_runs_successfully() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/verify_redteam_assets.py"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["cases_loaded"] >= 16
    assert "retrieved_context" in summary["channels"]
    assert "tool_output" in summary["channels"]
