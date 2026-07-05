#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from maci.redteam import RedTeamDatasetLoader  # noqa: E402
from maci.redteam_assets import REQUIRED_REDTEAM_ASSETS, missing_redteam_assets  # noqa: E402


def main() -> int:
    missing = missing_redteam_assets(ROOT)
    if missing:
        print("Missing red-team assets:", file=sys.stderr)
        for item in missing:
            print(f"- {item}", file=sys.stderr)
        return 1

    manifest = ROOT / "evals/redteam/dataset_manifest.example.json"
    cases = RedTeamDatasetLoader().load_manifests_file(manifest)
    if not cases:
        print("Manifest loaded zero cases", file=sys.stderr)
        return 1

    channels = sorted({case.channel.value for case in cases})
    datasets = sorted({case.source_dataset.value for case in cases})
    summary = {
        "required_assets": len(REQUIRED_REDTEAM_ASSETS),
        "cases_loaded": len(cases),
        "channels": channels,
        "datasets": datasets,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
