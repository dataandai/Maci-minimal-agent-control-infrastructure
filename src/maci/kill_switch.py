from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import Field

from .schemas import StrictModel, TenantContext


class KillSwitchScope(str, Enum):
    GLOBAL = "global"
    TENANT = "tenant"
    AGENT = "agent"
    TOOL = "tool"


class KillSwitchRecord(StrictModel):
    scope: KillSwitchScope
    key: str
    enabled: bool = True
    reason: str = Field(min_length=1)
    created_by: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KillSwitchBlocked(PermissionError):
    def __init__(self, record: KillSwitchRecord) -> None:
        super().__init__(f"kill switch active for {record.scope.value}:{record.key}: {record.reason}")
        self.record = record


class KillSwitchStore:
    """Global/tenant/agent/tool emergency stop state.

    This is deliberately independent from the circuit breaker. Circuit breakers
    are automatic safety controls. Kill switches are operator controls and must
    be checked before expensive or side-effectful work.
    """

    _local_records: dict[tuple[str, str], KillSwitchRecord] = {}

    def __init__(self, table_name: str | None = None) -> None:
        self.table_name = table_name or os.getenv("KILL_SWITCH_TABLE_NAME")
        self._table = None
        if self.table_name:
            try:
                import boto3  # type: ignore

                self._table = boto3.resource("dynamodb").Table(self.table_name)
            except Exception:
                self._table = None

    @staticmethod
    def key_for(scope: KillSwitchScope, key: str) -> tuple[str, str]:
        return (scope.value, key)

    def set(self, record: KillSwitchRecord) -> KillSwitchRecord:
        if self._table is not None:
            self._table.put_item(Item=record.model_dump(mode="json"))  # type: ignore[attr-defined]
        else:
            self._local_records[self.key_for(record.scope, record.key)] = record
        return record

    def clear(self, scope: KillSwitchScope, key: str) -> None:
        if self._table is not None:
            self._table.delete_item(Key={"scope": scope.value, "key": key})  # type: ignore[attr-defined]
        else:
            self._local_records.pop(self.key_for(scope, key), None)

    def get(self, scope: KillSwitchScope, key: str) -> KillSwitchRecord | None:
        if self._table is not None:
            response = self._table.get_item(Key={"scope": scope.value, "key": key})  # type: ignore[attr-defined]
            item = response.get("Item")
            return KillSwitchRecord.model_validate(_from_dynamodb_item(item)) if item else None
        return self._local_records.get(self.key_for(scope, key))

    def active_for_context(self, tenant_context: TenantContext, *, tool_name: str | None = None) -> KillSwitchRecord | None:
        checks: list[tuple[KillSwitchScope, str]] = [(KillSwitchScope.GLOBAL, "*")]
        checks.append((KillSwitchScope.TENANT, tenant_context.tenant_id))
        if tenant_context.agent_id:
            checks.append((KillSwitchScope.AGENT, tenant_context.agent_id))
        if tool_name:
            checks.append((KillSwitchScope.TOOL, f"{tenant_context.tenant_id}:{tool_name}"))
            checks.append((KillSwitchScope.TOOL, tool_name))
        for scope, key in checks:
            record = self.get(scope, key)
            if record and record.enabled:
                return record
        return None

    def enforce(self, tenant_context: TenantContext, *, tool_name: str | None = None) -> None:
        record = self.active_for_context(tenant_context, tool_name=tool_name)
        if record is not None:
            raise KillSwitchBlocked(record)


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
