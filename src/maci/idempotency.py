from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class TicketStore:
    """Small idempotent ticket store.

    In AWS, this uses DynamoDB with a deterministic ticket_key. Locally it uses an
    in-memory map so tests remain credential-free.
    """

    table_name: str | None = None
    table: object | None = None
    memory: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.table_name = self.table_name or os.getenv("TICKET_TABLE_NAME")
        if self.table_name and self.table is None:
            from ._aws import dynamodb_table

            self.table = dynamodb_table(self.table_name)

    def create_or_get(self, *, tenant_id: str, ticket_key: str, ticket_id: str, payload: dict[str, Any]) -> tuple[str, bool]:
        now = datetime.now(timezone.utc).isoformat()
        item = {
            "tenant_id": tenant_id,
            "ticket_key": ticket_key,
            "ticket_id": ticket_id,
            "payload": payload,
            "created_at": now,
        }
        if self.table is not None:
            try:
                self.table.put_item(  # type: ignore[attr-defined]
                    Item=item,
                    ConditionExpression="attribute_not_exists(tenant_id) AND attribute_not_exists(ticket_key)",
                )
                return ticket_id, True
            except Exception:
                existing = self.table.get_item(Key={"tenant_id": tenant_id, "ticket_key": ticket_key}).get("Item")  # type: ignore[attr-defined]
                if existing and existing.get("ticket_id"):
                    return str(existing["ticket_id"]), False
                raise

        key = (tenant_id, ticket_key)
        if key in self.memory:
            return str(self.memory[key]["ticket_id"]), False
        self.memory[key] = item
        return ticket_id, True


def deterministic_ticket_key(*, tenant_id: str, customer_id: str, title: str, description: str, request_id: str | None = None) -> str:
    base = "|".join([tenant_id, customer_id, title.strip().lower(), description.strip().lower(), request_id or ""])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:32]

@dataclass
class OperationIdempotencyStore:
    """Generic idempotency store for external writes and recovery-safe retries.

    Use this for operations that must not be executed twice after Lambda retry,
    Step Functions retry, redeploy, or manual recovery. The stored payload hash is
    part of the safety boundary: the same key cannot be reused for a different
    operation payload.
    """

    table_name: str | None = None
    table: object | None = None
    memory: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.table_name = self.table_name or os.getenv("IDEMPOTENCY_TABLE_NAME")
        if self.table_name and self.table is None:
            from ._aws import dynamodb_table

            self.table = dynamodb_table(self.table_name)

    def begin_or_get(self, *, tenant_id: str, idempotency_key: str, payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        payload_hash = deterministic_payload_hash(payload)
        now = datetime.now(timezone.utc).isoformat()
        item = {
            "tenant_id": tenant_id,
            "idempotency_key": idempotency_key,
            "payload_hash": payload_hash,
            "status": "started",
            "created_at": now,
            "updated_at": now,
            "result": None,
        }
        if self.table is not None:
            try:
                self.table.put_item(  # type: ignore[attr-defined]
                    Item=item,
                    ConditionExpression="attribute_not_exists(tenant_id) AND attribute_not_exists(idempotency_key)",
                )
                return item, True
            except Exception:
                existing = self.table.get_item(Key={"tenant_id": tenant_id, "idempotency_key": idempotency_key}).get("Item")  # type: ignore[attr-defined]
                _enforce_same_payload(existing, payload_hash)
                return existing, False

        key = (tenant_id, idempotency_key)
        existing = self.memory.get(key)
        if existing:
            _enforce_same_payload(existing, payload_hash)
            return existing, False
        self.memory[key] = item
        return item, True

    def complete(self, *, tenant_id: str, idempotency_key: str, result: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        if self.table is not None:
            self.table.update_item(  # type: ignore[attr-defined]
                Key={"tenant_id": tenant_id, "idempotency_key": idempotency_key},
                UpdateExpression="SET #status = :status, #result = :result, updated_at = :now",
                ExpressionAttributeNames={"#status": "status", "#result": "result"},
                ExpressionAttributeValues={":status": "completed", ":result": result, ":now": now},
            )
            return {"tenant_id": tenant_id, "idempotency_key": idempotency_key, "status": "completed", "result": result, "updated_at": now}
        key = (tenant_id, idempotency_key)
        item = self.memory[key]
        item.update({"status": "completed", "result": result, "updated_at": now})
        return item


def deterministic_operation_key(*, tenant_id: str, operation: str, resource_id: str, payload: dict[str, Any], approval_id: str | None = None) -> str:
    base = "|".join([tenant_id, operation, resource_id, approval_id or "", deterministic_payload_hash(payload)])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:40]


def deterministic_payload_hash(payload: dict[str, Any]) -> str:
    import json

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _enforce_same_payload(existing: dict[str, Any] | None, payload_hash: str) -> None:
    if not existing:
        raise RuntimeError("idempotency record exists but could not be loaded")
    if existing.get("payload_hash") != payload_hash:
        raise RuntimeError("idempotency key reused with different payload")
