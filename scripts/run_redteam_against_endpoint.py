#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from maci.redteam import LiveEndpointRedTeamRunner, RedTeamDatasetLoader


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Maci red-team dataset cases against a live dev/staging API endpoint.")
    parser.add_argument("--endpoint", required=True, help="Full agent API URL, for example https://abc.execute-api.../agent")
    parser.add_argument("--manifest", default="evals/redteam/dataset_manifest.example.json", help="Dataset manifest JSON file")
    parser.add_argument("--token-env", default="MACI_REDTEAM_JWT", help="Environment variable containing a test-tenant bearer token")
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--sleep-seconds", type=float, default=0.1, help="Delay between live requests to avoid accidental rate-limit noise")
    parser.add_argument("--output", default="", help="Optional JSON report path")
    parser.add_argument("--redteam-knowledge-base-id", default="kb-acme-support", help="Allowlisted test KB ID used for retrieved_context cases")
    parser.add_argument("--redteam-tool-name", default="customer_lookup", help="Allowlisted test tool name used for tool_output cases")
    args = parser.parse_args()

    token = os.getenv(args.token_env)
    if not token:
        print(f"Missing bearer token. Set {args.token_env}.", file=sys.stderr)
        return 2

    cases = RedTeamDatasetLoader().load_manifests_file(args.manifest)
    if not cases:
        print("No cases loaded from manifest.", file=sys.stderr)
        return 2

    runner = LiveEndpointRedTeamRunner(
        endpoint_url=args.endpoint,
        bearer_token=token,
        timeout_seconds=args.timeout_seconds,
        sleep_seconds=args.sleep_seconds,
        redteam_knowledge_base_id=args.redteam_knowledge_base_id,
        redteam_tool_name=args.redteam_tool_name,
    )
    result = runner.run_suite(cases)
    payload = result.model_dump(mode="json")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.output:
        Path(args.output).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
