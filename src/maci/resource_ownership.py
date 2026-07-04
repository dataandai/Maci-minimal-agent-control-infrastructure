from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

from .schemas import ResourceOwnerRecord, TenantContext


class ResourceOwnershipError(PermissionError):
    """Raised when a requested resource is not owned by the authenticated tenant."""


DEMO_RESOURCE_OWNERSHIP: dict[str, ResourceOwnerRecord] = {
    "cust-123": ResourceOwnerRecord(resource_id="cust-123", tenant_id="tenant-acme"),
    "acme-001": ResourceOwnerRecord(resource_id="acme-001", tenant_id="tenant-acme"),
    "contoso-001": ResourceOwnerRecord(resource_id="contoso-001", tenant_id="tenant-contoso"),
    "shared-prefix-001": ResourceOwnerRecord(resource_id="shared-prefix-001", tenant_id="tenant-contoso"),
}


class ResourceOwnershipStore:
    """Tenant/resource ownership lookup.

    Prefix allowlists are a useful local lab fallback, but production authorization
    should verify that the concrete resource belongs to the authenticated tenant.
    Set REQUIRE_RESOURCE_OWNERSHIP=true in staging/prod to fail closed when a
    resource is not present in the ownership table.
    """

    def __init__(self, table_name: str | None = None) -> None:
        self.table_name = table_name or os.getenv("RESOURCE_OWNERSHIP_TABLE_NAME")
        self._table = None
        if self.table_name:
            try:
                import boto3  # type: ignore

                self._table = boto3.resource("dynamodb").Table(self.table_name)
            except Exception:
                self._table = None

    def get_owner(self, resource_id: str) -> ResourceOwnerRecord | None:
        if self._table is not None:
            response = self._table.get_item(Key={"resource_id": resource_id})
            item = response.get("Item")
            return ResourceOwnerRecord.model_validate(_from_dynamodb_item(item)) if item else None
        return DEMO_RESOURCE_OWNERSHIP.get(resource_id)

    def enforce_owned_by_tenant(self, tenant_context: TenantContext, resource_id: str, *, require_known: bool | None = None) -> ResourceOwnerRecord | None:
        require = require_known if require_known is not None else os.getenv("REQUIRE_RESOURCE_OWNERSHIP", "false").lower() == "true"
        owner = self.get_owner(resource_id)
        if owner is None:
            if require:
                raise ResourceOwnershipError("resource ownership record not found")
            return None
        if owner.tenant_id != tenant_context.tenant_id:
            raise ResourceOwnershipError("resource owner tenant does not match authenticated tenant")
        if owner.status != "active":
            raise ResourceOwnershipError(f"resource is not active: {owner.status}")
        return owner


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
