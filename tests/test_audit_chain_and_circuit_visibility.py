from __future__ import annotations

from typing import Any

from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import ClientError

from maci.audit import AuditEvent, AuditEventType, AuditLogger
from maci.circuit_breaker import FailureCategory, TenantCircuitBreaker


_deserializer = TypeDeserializer()


def _from_av_map(raw: dict[str, Any]) -> dict[str, Any]:
    return {key: _deserializer.deserialize(value) for key, value in raw.items()}


class _FakeMeta:
    def __init__(self, client: object) -> None:
        self.client = client


class _FakeAuditClient:
    def __init__(self, table: "_FakeAuditTable") -> None:
        self.table = table

    def transact_write_items(self, TransactItems: list[dict[str, Any]]) -> None:  # noqa: N803 - boto3 shape
        update = TransactItems[0]["Update"]
        put = TransactItems[1]["Put"]
        head_key = tuple(_from_av_map(update["Key"]).values())
        head = self.table.items.get(head_key)
        condition = update["ConditionExpression"]
        values = {key: _deserializer.deserialize(value) for key, value in update["ExpressionAttributeValues"].items()}
        if condition == "attribute_not_exists(#seq)":
            if head and "sequence_number" in head:
                _raise_txn_cancelled()
        else:
            if not head or head.get("sequence_number") != values[":prev_seq"] or head.get("last_hash") != values[":prev_hash"]:
                _raise_txn_cancelled()

        event_item = _from_av_map(put["Item"])
        event_key = (event_item["tenant_id"], event_item["event_id"])
        if event_key in self.table.items:
            _raise_txn_cancelled()

        self.table.items[head_key] = {
            "tenant_id": head_key[0],
            "event_id": head_key[1],
            "last_hash": values[":last_hash"],
            "sequence_number": values[":seq"],
            "updated_at": values[":now"],
        }
        self.table.items[event_key] = event_item


class _FakeAuditTable:
    table_name = "fake-audit"

    def __init__(self) -> None:
        self.items: dict[tuple[str, str], dict[str, Any]] = {}
        self.meta = _FakeMeta(_FakeAuditClient(self))

    def get_item(self, Key: dict[str, Any], ConsistentRead: bool = False) -> dict[str, Any]:  # noqa: N803 - boto3 shape
        item = self.items.get((Key["tenant_id"], Key["event_id"]))
        return {"Item": item.copy()} if item else {}

    def put_item(self, Item: dict[str, Any]) -> None:  # noqa: N803 - fallback compatibility
        self.items[(Item["tenant_id"], Item["event_id"])] = Item


def _raise_txn_cancelled() -> None:
    raise ClientError({"Error": {"Code": "TransactionCanceledException", "Message": "condition failed"}}, "TransactWriteItems")


def test_dynamodb_audit_hash_chain_reads_shared_head_across_logger_instances():
    table = _FakeAuditTable()
    first_logger = AuditLogger(table=table)
    second_logger = AuditLogger(table=table)

    first_logger.emit(
        AuditEvent(request_id="req-chain", tenant_id="tenant-acme", event_type=AuditEventType.REQUEST_RECEIVED, message="first")
    )
    second_logger.emit(
        AuditEvent(request_id="req-chain", tenant_id="tenant-acme", event_type=AuditEventType.POLICY_ALLOWED, message="second")
    )

    events = [item for (_tenant, event_id), item in table.items.items() if not event_id.startswith("__")]
    events.sort(key=lambda item: item["sequence_number"])
    assert len(events) == 2
    assert events[0]["sequence_number"] == 1
    assert events[1]["sequence_number"] == 2
    assert events[1]["previous_event_hash"] == events[0]["event_hash"]


class _FakeCircuitTable:
    def __init__(self) -> None:
        self.items: dict[tuple[str, str], dict[str, Any]] = {}

    def update_item(self, Key: dict[str, str], UpdateExpression: str, ExpressionAttributeValues: dict[str, Any], ReturnValues: str):  # noqa: N803
        key = (Key["tenant_id"], Key["category"])
        item = self.items.setdefault(key, {"tenant_id": key[0], "category": key[1], "failure_count": 0})
        item["failure_count"] += int(ExpressionAttributeValues[":one"])
        item["updated_at_epoch"] = ExpressionAttributeValues[":now"]
        item["expires_at_epoch"] = ExpressionAttributeValues[":expires"]
        return {"Attributes": item.copy()}

    def get_item(self, Key: dict[str, str]) -> dict[str, Any]:  # noqa: N803
        item = self.items.get((Key["tenant_id"], Key["category"]))
        return {"Item": item.copy()} if item else {}

    def delete_item(self, Key: dict[str, str]) -> None:  # noqa: N803
        self.items.pop((Key["tenant_id"], Key["category"]), None)

    def query(self, KeyConditionExpression: object) -> dict[str, list[dict[str, Any]]]:  # noqa: N803
        # The production boto3 expression filters by tenant_id. For this unit fake
        # we keep the same bounded-per-tenant behavior by returning all records and
        # relying on the breaker test data to include only the target partition.
        return {"Items": [item.copy() for item in self.items.values() if item["tenant_id"] == "tenant-acme"]}


def test_dynamodb_tenant_circuit_breaker_any_category_reports_open_state():
    table = _FakeCircuitTable()
    breaker = TenantCircuitBreaker(threshold=1, table=table)
    assert breaker.record_failure("tenant-acme", FailureCategory.TOOL_NOT_ALLOWED) is True
    assert breaker.is_open("tenant-acme") is True
    assert breaker.is_open("tenant-acme", FailureCategory.TOOL_NOT_ALLOWED) is True
