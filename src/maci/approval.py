from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from .schemas import ApprovalRecord, ApprovalStatus, ResourceAction, RiskLevel, TenantContext, ToolName


class ApprovalError(PermissionError):
    """Raised when an approval is missing, rejected or malformed."""


def payload_fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def deterministic_approval_id(tenant_id: str, request_id: str, tool_name: str, resource_id: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(f"{tenant_id}|{request_id}|{tool_name}|{resource_id}|{payload_fingerprint(payload)}".encode()).hexdigest()[:24]
    return f"apr-{digest}"


class ApprovalStore:
    """Human-in-the-loop approval store with DynamoDB and local fallback."""

    _local_records: dict[tuple[str, str], ApprovalRecord] = {}

    def __init__(self, table_name: str | None = None) -> None:
        self.table_name = table_name or os.getenv("APPROVAL_TABLE_NAME")
        self._table = None
        if self.table_name:
            from ._aws import dynamodb_table

            self._table = dynamodb_table(self.table_name)

    def create_pending(
        self,
        tenant_context: TenantContext,
        *,
        tool_name: ToolName,
        resource_id: str,
        action: ResourceAction,
        risk_level: RiskLevel,
        payload: dict[str, Any],
    ) -> ApprovalRecord:
        approval_id = deterministic_approval_id(
            tenant_context.tenant_id,
            tenant_context.request_id,
            tool_name.value,
            resource_id,
            payload,
        )
        existing = self.get(tenant_context.tenant_id, approval_id)
        if existing:
            return existing
        record = ApprovalRecord(
            approval_id=approval_id,
            tenant_id=tenant_context.tenant_id,
            request_id=tenant_context.request_id,
            requested_by_user_id=tenant_context.user_id,
            tool_name=tool_name.value,
            resource_id=resource_id,
            action=action,
            risk_level=risk_level,
            payload=payload,
            payload_hash=payload_fingerprint(payload),
        )
        self._put(record)
        return record

    def get(self, tenant_id: str, approval_id: str) -> ApprovalRecord | None:
        if self._table is not None:
            response = self._table.get_item(Key={"tenant_id": tenant_id, "approval_id": approval_id})
            item = response.get("Item")
            return ApprovalRecord.model_validate(_from_dynamodb_item(item)) if item else None
        return self._local_records.get((tenant_id, approval_id))

    def approve(self, tenant_id: str, approval_id: str, *, decided_by_user_id: str, reason: str = "approved") -> ApprovalRecord:
        record = self.get(tenant_id, approval_id)
        if record is None:
            raise ApprovalError("approval record not found")
        # Segregation of duties: the person who requested a high-risk action must
        # not be able to approve it themselves, even if they also hold an approver
        # role. This is a hard control, not a UI convenience.
        if record.requested_by_user_id and record.requested_by_user_id == decided_by_user_id:
            raise ApprovalError("segregation of duties: requester cannot approve their own request")
        updated = record.model_copy(
            update={
                "status": ApprovalStatus.APPROVED,
                "decided_at": datetime.now(timezone.utc),
                "decided_by_user_id": decided_by_user_id,
                "decision_reason": reason,
            }
        )
        self._put(updated)
        return updated

    def reject(self, tenant_id: str, approval_id: str, *, decided_by_user_id: str, reason: str) -> ApprovalRecord:
        record = self.get(tenant_id, approval_id)
        if record is None:
            raise ApprovalError("approval record not found")
        updated = record.model_copy(
            update={
                "status": ApprovalStatus.REJECTED,
                "decided_at": datetime.now(timezone.utc),
                "decided_by_user_id": decided_by_user_id,
                "decision_reason": reason,
            }
        )
        self._put(updated)
        return updated

    def ensure_approved(self, tenant_id: str, approval_id: str, *, expected_action: ResourceAction, expected_resource_id: str, expected_payload: dict[str, Any] | None = None) -> ApprovalRecord:
        record = self.get(tenant_id, approval_id)
        if record is None:
            raise ApprovalError("approval record not found")
        if record.action != expected_action or record.resource_id != expected_resource_id:
            raise ApprovalError("approval record does not match requested operation")
        if expected_payload is not None and record.payload_hash != payload_fingerprint(expected_payload):
            raise ApprovalError("approval record does not match requested payload")
        if record.status == ApprovalStatus.REJECTED:
            raise ApprovalError("approval was rejected")
        if record.status != ApprovalStatus.APPROVED:
            raise ApprovalError("approval is still pending")
        return record

    def _put(self, record: ApprovalRecord) -> None:
        if self._table is not None:
            self._table.put_item(Item=_to_dynamodb_item(record.model_dump(mode="json")))
            return
        self._local_records[(record.tenant_id, record.approval_id)] = record


def _to_dynamodb_item(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _to_dynamodb_item(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_dynamodb_item(v) for v in value]
    return value


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
