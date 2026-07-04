#!/usr/bin/env python3
from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from maci.agent_registry import DEMO_AGENT_IDENTITIES  # noqa: E402
from maci.policy_store import DEMO_POLICIES  # noqa: E402
from maci.resource_ownership import DEMO_RESOURCE_OWNERSHIP  # noqa: E402
from maci.mcp_registry import DEMO_MCP_SERVERS  # noqa: E402


def to_dynamo(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, tuple):
        return [to_dynamo(v) for v in value]
    if isinstance(value, list):
        return [to_dynamo(v) for v in value]
    if isinstance(value, dict):
        return {k: to_dynamo(v) for k, v in value.items()}
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo tenant policies and optional agent identities into DynamoDB.")
    parser.add_argument("--table", required=True, help="Policy table name from Terraform/SAM output")
    parser.add_argument("--agent-registry-table", default=None, help="Optional agent registry table name")
    parser.add_argument("--resource-ownership-table", default=None, help="Optional resource ownership table name")
    parser.add_argument("--mcp-registry-table", default=None, help="Optional MCP server registry table name")
    parser.add_argument("--region", default=None)
    args = parser.parse_args()

    import boto3  # type: ignore

    dynamodb = boto3.resource("dynamodb", region_name=args.region)
    policy_table = dynamodb.Table(args.table)
    for policy in DEMO_POLICIES.values():
        item = to_dynamo(policy.model_dump(mode="json"))
        policy_table.put_item(Item=item)
        print(f"seeded policy {policy.tenant_id}")

    if args.agent_registry_table:
        agent_table = dynamodb.Table(args.agent_registry_table)
        for identity in DEMO_AGENT_IDENTITIES.values():
            item = to_dynamo(identity.model_dump(mode="json"))
            agent_table.put_item(Item=item)
            print(f"seeded agent {identity.agent_id}")

    if args.resource_ownership_table:
        ownership_table = dynamodb.Table(args.resource_ownership_table)
        for record in DEMO_RESOURCE_OWNERSHIP.values():
            item = to_dynamo(record.model_dump(mode="json"))
            ownership_table.put_item(Item=item)
            print(f"seeded resource ownership {record.resource_id} -> {record.tenant_id}")

    if args.mcp_registry_table:
        mcp_table = dynamodb.Table(args.mcp_registry_table)
        for record in DEMO_MCP_SERVERS.values():
            item = to_dynamo(record.model_dump(mode="json"))
            mcp_table.put_item(Item=item)
            print(f"seeded MCP server {record.server_id}")


if __name__ == "__main__":
    main()
