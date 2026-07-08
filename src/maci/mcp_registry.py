from __future__ import annotations

import hashlib
import json
import os
from decimal import Decimal
from typing import Any, Mapping

from pydantic import Field

from .schemas import StrictModel, TenantContext


class MCPServerRecord(StrictModel):
    server_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    allowed_tools: tuple[str, ...] = Field(default_factory=tuple)
    expected_fingerprint: str = Field(min_length=16)
    provenance: str = Field(min_length=1)
    enabled: bool = True


class MCPRegistryError(PermissionError):
    """Raised when an MCP server/tool source is not explicitly trusted."""


def canonical_mcp_manifest(record: MCPServerRecord) -> dict[str, Any]:
    """Return the minimal deterministic manifest this registry expects.

    A real MCP adapter should compute this from the concrete server manifest or
    signed attestation it fetched, then pass that manifest into the registry for
    verification. This keeps the policy layer from trusting a caller-supplied
    string without a canonical representation.
    """

    return {
        "server_id": record.server_id,
        "tenant_id": record.tenant_id,
        "base_url": record.base_url,
        "allowed_tools": sorted(record.allowed_tools),
        "provenance": record.provenance,
    }


def compute_mcp_manifest_fingerprint(manifest: Mapping[str, Any]) -> str:
    """Compute a stable sha256 fingerprint from an MCP manifest/attestation."""

    payload = json.dumps(_normalize_manifest(manifest), sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _normalize_manifest(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _normalize_manifest(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return sorted((_normalize_manifest(v) for v in value), key=lambda item: json.dumps(item, sort_keys=True, default=str))
    return value


_DEMO_MCP_BASE = {
    "server_id": "mcp-acme-tools",
    "tenant_id": "tenant-acme",
    "base_url": "https://mcp.example.internal/acme",
    "allowed_tools": ("customer_lookup", "ticket_creation", "billing_check"),
    "provenance": "demo-seeded",
}

DEMO_MCP_SERVERS: dict[str, MCPServerRecord] = {
    "mcp-acme-tools": MCPServerRecord(
        **_DEMO_MCP_BASE,
        expected_fingerprint=compute_mcp_manifest_fingerprint(_DEMO_MCP_BASE),
    )
}


class MCPServerRegistry:
    """Allowlisted MCP server provenance registry.

    A real MCP gateway should verify the concrete server/tool definition before
    it exposes a tool to an agent. This local implementation models the decision
    boundary without opening a network listener.
    """

    def __init__(self, table_name: str | None = None) -> None:
        self.table_name = table_name or os.getenv("MCP_REGISTRY_TABLE_NAME")
        self._table = None
        if self.table_name:
            from ._aws import dynamodb_table

            self._table = dynamodb_table(self.table_name)

    def get(self, server_id: str) -> MCPServerRecord:
        if self._table is not None:
            response = self._table.get_item(Key={"server_id": server_id})  # type: ignore[attr-defined]
            item = response.get("Item")
            if not item:
                raise MCPRegistryError(f"unknown MCP server: {server_id}")
            return MCPServerRecord.model_validate(_from_dynamodb_item(item))
        try:
            return DEMO_MCP_SERVERS[server_id]
        except KeyError as exc:
            raise MCPRegistryError(f"unknown MCP server: {server_id}") from exc

    def verify_server_for_tool(
        self,
        tenant_context: TenantContext,
        *,
        server_id: str,
        tool_name: str,
        presented_fingerprint: str | None = None,
        presented_manifest: Mapping[str, Any] | None = None,
    ) -> MCPServerRecord:
        record = self.get(server_id)
        if not record.enabled:
            raise MCPRegistryError("MCP server is disabled")
        if record.tenant_id != tenant_context.tenant_id:
            raise MCPRegistryError("MCP server tenant does not match authenticated tenant")
        if tool_name not in record.allowed_tools:
            raise MCPRegistryError(f"tool not allowed on MCP server: {tool_name}")

        computed_fingerprint: str | None = None
        if presented_manifest is not None:
            computed_fingerprint = compute_mcp_manifest_fingerprint(presented_manifest)
            if computed_fingerprint != record.expected_fingerprint:
                raise MCPRegistryError("MCP server manifest/provenance mismatch")

        if presented_fingerprint is None:
            presented_fingerprint = computed_fingerprint
        elif computed_fingerprint is not None and presented_fingerprint != computed_fingerprint:
            raise MCPRegistryError("presented MCP fingerprint does not match presented manifest")

        if presented_fingerprint != record.expected_fingerprint:
            raise MCPRegistryError("MCP server fingerprint/provenance mismatch")
        return record


def _from_dynamodb_item(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    if isinstance(value, set):
        return tuple(value)
    if isinstance(value, list):
        return [_from_dynamodb_item(v) for v in value]
    if isinstance(value, dict):
        return {k: _from_dynamodb_item(v) for k, v in value.items()}
    return value
