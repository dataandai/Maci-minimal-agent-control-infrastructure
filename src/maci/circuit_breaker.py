from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import time

try:  # Optional runtime dependency in local tests.
    from boto3.dynamodb.conditions import Key  # type: ignore
except Exception:  # pragma: no cover
    Key = None  # type: ignore


class FailureCategory(str, Enum):
    SCHEMA_VALIDATION_FAILED = "schema_validation_failed"
    TOOL_NOT_ALLOWED = "tool_not_allowed"
    MODEL_NOT_ALLOWED = "model_not_allowed"
    TENANT_BUDGET_EXCEEDED = "tenant_budget_exceeded"
    BEDROCK_THROTTLED = "bedrock_throttled"
    GUARDRAIL_INTERVENED = "guardrail_intervened"
    KNOWLEDGE_BASE_DENIED = "knowledge_base_denied"
    LAMBDA_TOOL_TIMEOUT = "lambda_tool_timeout"
    UNKNOWN = "unknown"


@dataclass
class CircuitBreaker:
    """Simple in-memory circuit breaker for local validation and examples.

    In production, store state in DynamoDB/ElastiCache or use workflow state.
    """

    threshold: int = 3
    counts: dict[FailureCategory, int] = field(default_factory=dict)
    open_categories: set[FailureCategory] = field(default_factory=set)

    def record_failure(self, category: FailureCategory) -> bool:
        self.counts[category] = self.counts.get(category, 0) + 1
        if self.counts[category] >= self.threshold:
            self.open_categories.add(category)
        return self.is_open(category)

    def record_success(self, category: FailureCategory) -> None:
        self.counts[category] = 0
        self.open_categories.discard(category)

    def is_open(self, category: FailureCategory | None = None) -> bool:
        if category is None:
            return bool(self.open_categories)
        return category in self.open_categories


@dataclass
class TenantCircuitBreaker:
    """Tenant-scoped circuit breaker with optional DynamoDB persistence.

    DynamoDB is used only when a table object is supplied. Local tests can use
    the in-memory fallback. The storage key is tenant_id + category, which avoids
    one tenant poisoning another tenant's failure state.
    """

    threshold: int = 3
    open_seconds: int = 300
    table: object | None = None
    counts: dict[tuple[str, FailureCategory], int] = field(default_factory=dict)
    open_categories: set[tuple[str, FailureCategory]] = field(default_factory=set)

    def record_failure(self, tenant_id: str, category: FailureCategory) -> bool:
        key = (tenant_id, category)
        if self.table is not None:
            response = self.table.update_item(  # type: ignore[attr-defined]
                Key={"tenant_id": tenant_id, "category": category.value},
                UpdateExpression="ADD failure_count :one SET updated_at_epoch = :now, expires_at_epoch = :expires",
                ExpressionAttributeValues={":one": 1, ":now": int(time()), ":expires": int(time()) + self.open_seconds},
                ReturnValues="ALL_NEW",
            )
            count = int(response["Attributes"].get("failure_count", 0))
        else:
            self.counts[key] = self.counts.get(key, 0) + 1
            count = self.counts[key]
        if count >= self.threshold:
            self.open_categories.add(key)
        return self.is_open(tenant_id, category)

    def record_success(self, tenant_id: str, category: FailureCategory) -> None:
        key = (tenant_id, category)
        if self.table is not None:
            self.table.delete_item(Key={"tenant_id": tenant_id, "category": category.value})  # type: ignore[attr-defined]
        else:
            self.counts[key] = 0
        self.open_categories.discard(key)

    def is_open(self, tenant_id: str, category: FailureCategory | None = None) -> bool:
        if self.table is not None and category is not None:
            response = self.table.get_item(Key={"tenant_id": tenant_id, "category": category.value})  # type: ignore[attr-defined]
            item = response.get("Item")
            if not item:
                return False
            expires_at = int(item.get("expires_at_epoch", 0))
            if expires_at and expires_at < int(time()):
                self.record_success(tenant_id, category)
                return False
            return int(item.get("failure_count", 0)) >= self.threshold
        if self.table is not None and category is None:
            # Query this tenant's categories instead of returning a blind false.
            # The table is keyed by tenant_id + category, so this is bounded to a
            # single tenant partition and does not require a cross-tenant scan.
            if Key is None:  # pragma: no cover - boto3 is present in deployed Lambdas
                return False
            response = self.table.query(KeyConditionExpression=Key("tenant_id").eq(tenant_id))  # type: ignore[attr-defined]
            now = int(time())
            for item in response.get("Items", []):
                expires_at = int(item.get("expires_at_epoch", 0))
                category_value = item.get("category")
                if expires_at and expires_at < now and category_value:
                    try:
                        self.record_success(tenant_id, FailureCategory(category_value))
                    except ValueError:
                        pass
                    continue
                if int(item.get("failure_count", 0)) >= self.threshold:
                    return True
            return False
        if category is not None:
            return (tenant_id, category) in self.open_categories
        return any(key_tenant == tenant_id for key_tenant, _ in self.open_categories)
