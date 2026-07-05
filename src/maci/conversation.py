from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import Field

from .schemas import StrictModel, TenantContext


class ConversationStatus(str, Enum):
    OPEN = "open"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    FAILED_SAFE = "failed_safe"
    ESCALATED_TO_HUMAN = "escalated_to_human"


class ConversationMessageType(str, Enum):
    USER_MESSAGE = "user_message"
    ASSISTANT_MESSAGE = "assistant_message"
    TOOL_RESULT_SUMMARY = "tool_result_summary"
    APPROVAL_STATUS = "approval_status"
    SYSTEM_STATUS = "system_status"


class ConversationRecord(StrictModel):
    conversation_id: str = Field(default_factory=lambda: f"conv-{uuid4().hex[:24]}")
    tenant_id: str
    created_by_user_id: str
    agent_id: str | None = None
    status: ConversationStatus = ConversationStatus.OPEN
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_message_id: str | None = None
    transcript_s3_prefix: str | None = None
    retention_until: datetime | None = None
    contains_pii: bool = False
    legal_hold: bool = False


class ConversationMessage(StrictModel):
    conversation_id: str
    message_id: str = Field(default_factory=lambda: f"msg-{uuid4().hex[:24]}")
    request_id: str
    tenant_id: str
    actor_type: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    message_type: ConversationMessageType
    content: str | dict[str, Any]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    visible_to_user: bool = True
    redaction_status: str = "none"


@dataclass
class ConversationStore:
    """Tenant-scoped conversation transcript store.

    DynamoDB stores searchable metadata and message index records. S3 optionally
    stores immutable message objects under a tenant/conversation prefix. Local
    memory mode keeps tests and demos credential-free.

    This is intentionally separate from the audit trail: transcripts explain the
    conversation to users; audit events prove security/business decisions.
    """

    table_name: str | None = None
    transcript_bucket: str | None = None
    table: object | None = None
    s3_client: object | None = None
    memory_records: dict[tuple[str, str], ConversationRecord] = field(default_factory=dict)
    memory_messages: dict[tuple[str, str], list[ConversationMessage]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.table_name = self.table_name or os.getenv("CONVERSATION_TABLE_NAME")
        self.transcript_bucket = self.transcript_bucket or os.getenv("CONVERSATION_TRANSCRIPT_BUCKET")
        if (self.table_name or self.transcript_bucket) and (self.table is None and self.s3_client is None):
            try:
                import boto3  # type: ignore

                if self.table_name:
                    self.table = boto3.resource("dynamodb").Table(self.table_name)
                if self.transcript_bucket:
                    self.s3_client = boto3.client("s3")
            except Exception:
                self.table = None
                self.s3_client = None

    def start_or_resume(
        self,
        tenant_context: TenantContext,
        *,
        conversation_id: str | None = None,
        retention_days: int = 90,
        contains_pii: bool = True,
    ) -> ConversationRecord:
        if conversation_id and tenant_context.conversation_id and conversation_id != tenant_context.conversation_id:
            raise ValueError("request conversation_id does not match authenticated conversation claim")

        conversation_id = tenant_context.conversation_id or conversation_id or f"conv-{tenant_context.request_id}"
        existing = self.get(tenant_context.tenant_id, conversation_id)
        if existing:
            if existing.created_by_user_id != tenant_context.user_id:
                raise ValueError("conversation_id is already owned by another user in this tenant")
            return existing
        now = datetime.now(timezone.utc)
        record = ConversationRecord(
            conversation_id=conversation_id,
            tenant_id=tenant_context.tenant_id,
            created_by_user_id=tenant_context.user_id,
            agent_id=tenant_context.agent_id,
            created_at=now,
            updated_at=now,
            transcript_s3_prefix=_transcript_prefix(tenant_context.tenant_id, conversation_id, now),
            retention_until=now + timedelta(days=retention_days),
            contains_pii=contains_pii,
        )
        return self._put_new_record(record)

    def get(self, tenant_id: str, conversation_id: str) -> ConversationRecord | None:
        if self.table is not None:
            item = self.table.get_item(Key={"tenant_id": tenant_id, "record_key": f"CONVERSATION#{conversation_id}"}).get("Item")  # type: ignore[attr-defined]
            return ConversationRecord.model_validate(_from_dynamodb_item(item)) if item else None
        return self.memory_records.get((tenant_id, conversation_id))

    def append_message(self, message: ConversationMessage) -> ConversationMessage:
        self._put_message(message)
        existing = self.get(message.tenant_id, message.conversation_id)
        if existing:
            self._put_record(
                existing.model_copy(
                    update={
                        "updated_at": datetime.now(timezone.utc),
                        "last_message_id": message.message_id,
                    }
                )
            )
        self._archive_message(message)
        return message

    def append_user_message(self, tenant_context: TenantContext, conversation_id: str, content: str) -> ConversationMessage:
        return self.append_message(
            ConversationMessage(
                conversation_id=conversation_id,
                request_id=tenant_context.request_id,
                tenant_id=tenant_context.tenant_id,
                actor_type="user",
                actor_id=tenant_context.user_id,
                message_type=ConversationMessageType.USER_MESSAGE,
                content=content,
                redaction_status="none",
            )
        )

    def append_assistant_message(self, tenant_context: TenantContext, conversation_id: str, content: str) -> ConversationMessage:
        return self.append_message(
            ConversationMessage(
                conversation_id=conversation_id,
                request_id=tenant_context.request_id,
                tenant_id=tenant_context.tenant_id,
                actor_type="assistant",
                actor_id=tenant_context.agent_id or "maci-agent",
                message_type=ConversationMessageType.ASSISTANT_MESSAGE,
                content=content,
                redaction_status="none",
            )
        )

    def append_system_status(self, tenant_context: TenantContext, conversation_id: str, content: dict[str, Any]) -> ConversationMessage:
        return self.append_message(
            ConversationMessage(
                conversation_id=conversation_id,
                request_id=tenant_context.request_id,
                tenant_id=tenant_context.tenant_id,
                actor_type="system",
                actor_id="maci-control-plane",
                message_type=ConversationMessageType.SYSTEM_STATUS,
                content=content,
                visible_to_user=False,
                redaction_status="redacted",
            )
        )


    def append_tool_result_summary(self, tenant_context: TenantContext, conversation_id: str, tool_name: str, content: dict[str, Any]) -> ConversationMessage:
        return self.append_message(
            ConversationMessage(
                conversation_id=conversation_id,
                request_id=tenant_context.request_id,
                tenant_id=tenant_context.tenant_id,
                actor_type="tool",
                actor_id=tool_name,
                message_type=ConversationMessageType.TOOL_RESULT_SUMMARY,
                content=content,
                visible_to_user=True,
                redaction_status="redacted",
            )
        )

    def append_approval_status(self, tenant_context: TenantContext, conversation_id: str, content: dict[str, Any]) -> ConversationMessage:
        return self.append_message(
            ConversationMessage(
                conversation_id=conversation_id,
                request_id=tenant_context.request_id,
                tenant_id=tenant_context.tenant_id,
                actor_type="system",
                actor_id="maci-approval-workflow",
                message_type=ConversationMessageType.APPROVAL_STATUS,
                content=content,
                visible_to_user=True,
                redaction_status="redacted",
            )
        )

    def update_status(self, tenant_id: str, conversation_id: str, status: ConversationStatus) -> ConversationRecord:
        record = self.get(tenant_id, conversation_id)
        if record is None:
            raise KeyError(f"conversation not found: {conversation_id}")
        updated = record.model_copy(update={"status": status, "updated_at": datetime.now(timezone.utc)})
        self._put_record(updated)
        return updated

    def list_messages(self, tenant_id: str, conversation_id: str) -> tuple[ConversationMessage, ...]:
        if self.table is not None:
            response = self.table.query(  # type: ignore[attr-defined]
                KeyConditionExpression="tenant_id = :tenant AND begins_with(record_key, :prefix)",
                ExpressionAttributeValues={":tenant": tenant_id, ":prefix": f"CONVERSATION#{conversation_id}#MESSAGE#"},
            )
            items = response.get("Items", [])
            messages = [ConversationMessage.model_validate(_from_dynamodb_item(item.get("message", item))) for item in items]
            return tuple(sorted(messages, key=lambda msg: msg.created_at))
        return tuple(self.memory_messages.get((tenant_id, conversation_id), []))


    def _put_new_record(self, record: ConversationRecord) -> ConversationRecord:
        """Create a conversation record without clobbering another owner.

        The pre-read ownership check in start_or_resume is not sufficient under
        concurrency: two users in the same tenant could race on a guessable
        conversation_id. DynamoDB uses a conditional put; local mode uses the
        same owner check before inserting.
        """

        if self.table is not None:
            item = record.model_dump(mode="json")
            item["record_key"] = f"CONVERSATION#{record.conversation_id}"
            try:
                self.table.put_item(  # type: ignore[attr-defined]
                    Item=_to_dynamodb_item(item),
                    ConditionExpression="attribute_not_exists(tenant_id) AND attribute_not_exists(record_key)",
                )
                return record
            except Exception:
                existing = self.get(record.tenant_id, record.conversation_id)
                if existing is not None and existing.created_by_user_id == record.created_by_user_id:
                    return existing
                if existing is not None:
                    raise ValueError("conversation_id is already owned by another user in this tenant")
                raise

        existing = self.memory_records.get((record.tenant_id, record.conversation_id))
        if existing is not None:
            if existing.created_by_user_id != record.created_by_user_id:
                raise ValueError("conversation_id is already owned by another user in this tenant")
            return existing
        self.memory_records[(record.tenant_id, record.conversation_id)] = record
        return record

    def _put_record(self, record: ConversationRecord) -> None:
        if self.table is not None:
            item = record.model_dump(mode="json")
            item["record_key"] = f"CONVERSATION#{record.conversation_id}"
            self.table.put_item(Item=_to_dynamodb_item(item))  # type: ignore[attr-defined]
            return
        self.memory_records[(record.tenant_id, record.conversation_id)] = record

    def _put_message(self, message: ConversationMessage) -> None:
        if self.table is not None:
            item = message.model_dump(mode="json")
            item["record_key"] = f"CONVERSATION#{message.conversation_id}#MESSAGE#{message.created_at.isoformat()}#{message.message_id}"
            item["message"] = message.model_dump(mode="json")
            self.table.put_item(Item=_to_dynamodb_item(item))  # type: ignore[attr-defined]
            return
        self.memory_messages.setdefault((message.tenant_id, message.conversation_id), []).append(message)

    def _archive_message(self, message: ConversationMessage) -> None:
        if self.s3_client is None or not self.transcript_bucket:
            return
        key = f"{_transcript_prefix(message.tenant_id, message.conversation_id, message.created_at)}/messages/{message.created_at.isoformat()}-{message.message_id}.json"
        self.s3_client.put_object(  # type: ignore[attr-defined]
            Bucket=self.transcript_bucket,
            Key=key,
            Body=(json.dumps(message.model_dump(mode="json"), sort_keys=True) + "\n").encode("utf-8"),
            ContentType="application/json",
        )


def _transcript_prefix(tenant_id: str, conversation_id: str, created_at: datetime) -> str:
    day = created_at.date().isoformat()
    return f"tenant_id={tenant_id}/date={day}/conversation_id={conversation_id}"


def _to_dynamodb_item(value: Any) -> Any:
    from decimal import Decimal

    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _to_dynamodb_item(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_to_dynamodb_item(v) for v in value]
    return value


def _from_dynamodb_item(value: Any) -> Any:
    from decimal import Decimal

    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    if isinstance(value, dict):
        return {k: _from_dynamodb_item(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_from_dynamodb_item(v) for v in value]
    return value
