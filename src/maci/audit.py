from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import Field

from .redaction import RedactionService, finding_labels
from .schemas import StrictModel


class AuditEventType(str, Enum):
    REQUEST_RECEIVED = "request_received"
    POLICY_ALLOWED = "policy_allowed"
    POLICY_DENIED = "policy_denied"
    MODEL_INVOKED = "model_invoked"
    KNOWLEDGE_BASE_RETRIEVED = "knowledge_base_retrieved"
    TOOL_INVOKED = "tool_invoked"
    TOOL_AUTHORIZED = "tool_authorized"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_DECIDED = "approval_decided"
    GUARDRAIL_INTERVENED = "guardrail_intervened"
    SCHEMA_VALIDATION_FAILED = "schema_validation_failed"
    CIRCUIT_BREAKER_TRIPPED = "circuit_breaker_tripped"
    TRACE_RECORDED = "trace_recorded"
    RECOVERY_ACTION = "recovery_action"


class AuditEvent(StrictModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    request_id: str
    tenant_id: str
    event_type: AuditEventType
    message: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    previous_event_hash: str | None = None
    event_hash: str | None = None
    sequence_number: int | None = None


_AUDIT_CHAIN_HEAD_EVENT_ID = "__AUDIT_CHAIN_HEAD__"
_MAX_CHAIN_RETRIES = 5


class AuditLogger:
    """Audit sink with DynamoDB, optional S3 archive, and local fallback.

    DynamoDB supports hot operational lookup by tenant_id/event_id. S3 provides
    the append-only archive path; enable Object Lock on the bucket in Terraform
    for tamper-evident/compliance deployments.

    Hash-chain note:
    - local/no-DynamoDB mode keeps a per-process chain for tests and demos;
    - DynamoDB mode uses a per-tenant chain-head record and TransactWriteItems
      so concurrent Lambda containers do not fork the hash chain.
    """

    _last_hash_by_tenant: dict[str, str] = {}
    _last_sequence_by_tenant: dict[str, int] = {}

    def __init__(self, table_name: str | None = None, archive_bucket: str | None = None, table: object | None = None, redactor: RedactionService | None = None) -> None:
        self.table_name = table_name or os.getenv("AUDIT_TABLE_NAME")
        self.archive_bucket = archive_bucket or os.getenv("AUDIT_ARCHIVE_BUCKET")
        self._table = table
        self._s3 = None
        self._redactor = redactor or RedactionService()
        if self._table is None and self.table_name:
            from ._aws import dynamodb_table

            self._table = dynamodb_table(self.table_name)
        if self._s3 is None and self.archive_bucket:
            from ._aws import s3_client

            self._s3 = s3_client()

    def emit(self, event: AuditEvent) -> None:
        event = self._redact_event(event)
        if self._table is not None:
            item = self._emit_dynamodb_chained(event)
        else:
            item = self._emit_local_chained(event)

        if self._s3 is not None and self.archive_bucket:
            key = _archive_key(item)
            self._s3.put_object(
                Bucket=self.archive_bucket,
                Key=key,
                Body=(json.dumps(item, sort_keys=True) + "\n").encode("utf-8"),
                ContentType="application/json",
            )
        if self._table is None and self._s3 is None:
            print(json.dumps(item, sort_keys=True))


    def _redact_event(self, event: AuditEvent) -> AuditEvent:
        message_result = self._redactor.redact_text(event.message, path="audit.message")
        attributes_result = self._redactor.redact_value(event.attributes, path="audit.attributes")
        findings = (*message_result.findings, *attributes_result.findings)
        if not findings:
            return event
        attributes = dict(attributes_result.value) if isinstance(attributes_result.value, dict) else {"redacted_attributes": attributes_result.value}
        attributes["pii_redaction_status"] = "redacted"
        attributes["pii_findings"] = finding_labels(findings)
        return event.model_copy(update={"message": message_result.value, "attributes": attributes})

    def _emit_local_chained(self, event: AuditEvent) -> dict[str, Any]:
        item = event.model_dump(mode="json")
        previous_hash = event.previous_event_hash or self._last_hash_by_tenant.get(event.tenant_id)
        previous_sequence = self._last_sequence_by_tenant.get(event.tenant_id, 0)
        item = _prepare_hashed_item(item, previous_hash=previous_hash, sequence_number=previous_sequence + 1)
        self._last_hash_by_tenant[event.tenant_id] = item["event_hash"]
        self._last_sequence_by_tenant[event.tenant_id] = int(item["sequence_number"])
        return item

    def _emit_dynamodb_chained(self, event: AuditEvent) -> dict[str, Any]:
        """Append an audit event and advance the per-tenant chain head atomically.

        The previous v0.1.2 local-hardening implementation read the previous hash
        only from a process-local dictionary. That is fine for single-process
        tests, but it forks under Lambda concurrency. This path reads the chain
        head from DynamoDB and uses TransactWriteItems with a conditional update
        so competing writers retry instead of producing divergent chains.
        """
        if not _supports_dynamodb_transaction(self._table):
            item = self._emit_local_chained(event)
            self._table.put_item(Item=item)  # type: ignore[attr-defined]
            return item

        tenant_id = event.tenant_id
        head_key = {"tenant_id": tenant_id, "event_id": _AUDIT_CHAIN_HEAD_EVENT_ID}
        last_error: Exception | None = None
        for _ in range(_MAX_CHAIN_RETRIES):
            head_response = self._table.get_item(Key=head_key, ConsistentRead=True)  # type: ignore[attr-defined]
            head = head_response.get("Item") or {}
            previous_hash = event.previous_event_hash or head.get("last_hash")
            previous_sequence = int(head.get("sequence_number", 0) or 0)
            item = _prepare_hashed_item(
                event.model_dump(mode="json"),
                previous_hash=previous_hash,
                sequence_number=previous_sequence + 1,
            )
            try:
                _transact_append_event(self._table, head_key, item, previous_hash, previous_sequence)  # type: ignore[arg-type]
                self._last_hash_by_tenant[tenant_id] = item["event_hash"]
                self._last_sequence_by_tenant[tenant_id] = int(item["sequence_number"])
                return item
            except Exception as exc:  # pragma: no cover - exact boto exception class varies
                last_error = exc
                if _is_retryable_chain_conflict(exc):
                    continue
                raise
        raise RuntimeError("audit_hash_chain_conflict_after_retries") from last_error


def _prepare_hashed_item(item: dict[str, Any], previous_hash: str | None, sequence_number: int) -> dict[str, Any]:
    item["previous_event_hash"] = previous_hash
    item["sequence_number"] = sequence_number
    item["event_hash"] = _event_hash(item)
    return item


def _supports_dynamodb_transaction(table: object) -> bool:
    return bool(getattr(table, "table_name", None) and getattr(getattr(table, "meta", None), "client", None))


def _transact_append_event(
    table: object,
    head_key: dict[str, Any],
    item: dict[str, Any],
    previous_hash: str | None,
    previous_sequence: int,
) -> None:
    from boto3.dynamodb.types import TypeSerializer  # type: ignore

    serializer = TypeSerializer()

    def av(value: Any) -> dict[str, Any]:
        return serializer.serialize(value)

    def av_item(raw: dict[str, Any]) -> dict[str, Any]:
        return {key: av(value) for key, value in raw.items() if value is not None}

    table_name = getattr(table, "table_name")
    client = table.meta.client  # type: ignore[attr-defined]
    now = datetime.now(timezone.utc).isoformat()
    expression_values: dict[str, Any] = {
        ":last_hash": av(item["event_hash"]),
        ":seq": av(int(item["sequence_number"])),
        ":now": av(now),
    }
    if previous_hash is None and previous_sequence == 0:
        condition = "attribute_not_exists(#seq)"
    else:
        condition = "#seq = :prev_seq AND last_hash = :prev_hash"
        expression_values[":prev_seq"] = av(previous_sequence)
        expression_values[":prev_hash"] = av(previous_hash)

    client.transact_write_items(
        TransactItems=[
            {
                "Update": {
                    "TableName": table_name,
                    "Key": av_item(head_key),
                    "UpdateExpression": "SET last_hash = :last_hash, #seq = :seq, updated_at = :now",
                    "ConditionExpression": condition,
                    "ExpressionAttributeNames": {"#seq": "sequence_number"},
                    "ExpressionAttributeValues": expression_values,
                }
            },
            {
                "Put": {
                    "TableName": table_name,
                    "Item": av_item(item),
                    "ConditionExpression": "attribute_not_exists(event_id)",
                }
            },
        ]
    )


def _is_retryable_chain_conflict(exc: Exception) -> bool:
    response = getattr(exc, "response", {}) or {}
    code = response.get("Error", {}).get("Code", "")
    return code in {"TransactionCanceledException", "ConditionalCheckFailedException"} or "TransactionCanceled" in type(exc).__name__


def _event_hash(item: dict[str, Any]) -> str:
    stable = {k: v for k, v in item.items() if k != "event_hash"}
    return hashlib.sha256(json.dumps(stable, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _archive_key(item: dict[str, Any]) -> str:
    created = str(item.get("created_at", datetime.now(timezone.utc).isoformat()))
    date = created[:10]
    tenant_id = str(item.get("tenant_id", "unknown"))
    event_id = str(item.get("event_id", uuid4()))
    return f"tenant_id={tenant_id}/date={date}/{event_id}.json"
