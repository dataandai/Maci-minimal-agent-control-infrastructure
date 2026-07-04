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
            try:
                import boto3  # type: ignore

                self.table = boto3.resource("dynamodb").Table(self.table_name)
            except Exception:
                self.table = None

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
