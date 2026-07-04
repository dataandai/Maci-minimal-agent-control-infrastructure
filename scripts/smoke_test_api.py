#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser(description="Invoke the governed API endpoint with a JWT token.")
    parser.add_argument("--url", required=True)
    parser.add_argument("--id-token", required=True)
    parser.add_argument("--tenant-id", default="tenant-acme", help="Expected tenant for optional echo testing; identity still comes from JWT")
    parser.add_argument("--user-id", default=None, help="Optional expected user echo")
    parser.add_argument("--include-identity-echo", action="store_true", help="Include tenant_id/user_id compatibility echo fields in the body")
    args = parser.parse_args()

    body = {
        "task_type": "support_answer",
        "input": "How can I reset SSO settings?",
        "requested_model": "anthropic.claude-3-5-sonnet-20241022-v2:0",
    }
    if args.include_identity_echo:
        body["tenant_id"] = args.tenant_id
        if args.user_id:
            body["user_id"] = args.user_id

    request = urllib.request.Request(
        args.url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {args.id_token}", "content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        print(response.status)
        print(response.read().decode("utf-8"))


if __name__ == "__main__":
    main()
