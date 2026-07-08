from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from pydantic import Field

from .schemas import StrictModel


class TokenUsage(StrictModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class CostEstimate(StrictModel):
    model_id: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    pricing_source: str


class UsageLedgerEvent(StrictModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    request_id: str
    tenant_id: str
    user_id: str
    model_id: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Sample defaults only. Replace with live AWS Pricing API / account-approved pricing config
# before using for chargeback. Values are intentionally conservative placeholders.
_DEFAULT_PRICING_PER_1K: dict[str, tuple[float, float]] = {
    "anthropic.claude-3-5-sonnet-20241022-v2:0": (0.003, 0.015),
    "amazon.nova-pro-v1:0": (0.0008, 0.0032),
    "amazon.nova-lite-v1:0": (0.00006, 0.00024),
}


@dataclass(frozen=True)
class CostEstimator:
    """Token-based cost estimator.

    This is a control-plane estimator, not a billing source of truth. Production
    deployments should feed this from an approved pricing config or the AWS
    Pricing API and reconcile it against Cost Explorer/CUR.
    """

    pricing_per_1k_tokens: dict[str, tuple[float, float]] | None = None

    def estimate_request_cost(self, model_id: str, input_chars: int, max_output_tokens: int) -> CostEstimate:
        approx_input_tokens = max(1, input_chars // 4)
        return self.estimate_usage_cost(model_id, approx_input_tokens, max_output_tokens)

    def estimate_usage_cost(self, model_id: str, input_tokens: int, output_tokens: int) -> CostEstimate:
        table = self.pricing_per_1k_tokens or _DEFAULT_PRICING_PER_1K
        input_rate, output_rate = table.get(model_id, (0.002, 0.01))
        estimated_cost = (input_tokens / 1000.0 * input_rate) + (output_tokens / 1000.0 * output_rate)
        return CostEstimate(
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=round(estimated_cost, 8),
            pricing_source="sample_static_pricing_table",
        )


class UsageLedger:
    """Optional DynamoDB-backed usage ledger with local no-op fallback."""

    def __init__(
        self,
        usage_table_name: str | None = None,
        policy_table_name: str | None = None,
    ) -> None:
        self.usage_table_name = usage_table_name or os.getenv("USAGE_TABLE_NAME")
        self.policy_table_name = policy_table_name or os.getenv("POLICY_TABLE_NAME")
        self._usage_table = None
        self._policy_table = None
        if self.usage_table_name or self.policy_table_name:
            from ._aws import dynamodb_table

            if self.usage_table_name:
                self._usage_table = dynamodb_table(self.usage_table_name)
            if self.policy_table_name:
                self._policy_table = dynamodb_table(self.policy_table_name)

    def record(self, event: UsageLedgerEvent) -> None:
        if self._usage_table is not None:
            self._usage_table.put_item(Item=_to_dynamodb_item(event.model_dump(mode="json")))

        if self._policy_table is not None:
            self._policy_table.update_item(
                Key={"tenant_id": event.tenant_id},
                UpdateExpression="ADD current_month_spend_usd :cost",
                ExpressionAttributeValues={":cost": Decimal(str(event.estimated_cost_usd))},
            )


def _to_dynamodb_item(value: Any) -> Any:
    """Convert Python floats to Decimal for DynamoDB compatibility."""

    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _to_dynamodb_item(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_dynamodb_item(v) for v in value]
    return value
