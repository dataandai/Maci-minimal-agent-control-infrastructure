from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

from .schemas import ResourceAction, TenantPolicy


DEMO_POLICIES: dict[str, TenantPolicy] = {
    "tenant-acme": TenantPolicy(
        tenant_id="tenant-acme",
        allowed_models=("anthropic.claude-sonnet-5", "amazon.nova-pro-v1:0"),
        allowed_knowledge_base_ids=("kb-acme-support",),
        allowed_tools=("customer_lookup", "ticket_creation", "billing_check", "account_credit"),
        max_input_chars=12000,
        max_output_tokens=2048,
        monthly_budget_usd=500.0,
        current_month_spend_usd=125.0,
        allowed_customer_id_prefixes=("cust-", "acme-"),
        allowed_resource_actions=(ResourceAction.READ_CUSTOMER, ResourceAction.CREATE_TICKET, ResourceAction.READ_BILLING, ResourceAction.ISSUE_CREDIT),
        high_risk_tools=("account_credit",),
        human_approval_required_tools=("account_credit",),
        allowed_agent_ids=("agent-acme-support", "agent-acme-billing-risk"),
        guardrail_identifier="gr-acme-support",
        guardrail_version="DRAFT",
    ),
    "tenant-contoso": TenantPolicy(
        tenant_id="tenant-contoso",
        allowed_models=("amazon.nova-lite-v1:0",),
        allowed_knowledge_base_ids=("kb-contoso-support",),
        allowed_tools=("customer_lookup",),
        max_input_chars=8000,
        max_output_tokens=1024,
        monthly_budget_usd=100.0,
        current_month_spend_usd=80.0,
        allowed_customer_id_prefixes=("contoso-", "cust-"),
        allowed_resource_actions=(ResourceAction.READ_CUSTOMER,),
        allowed_agent_ids=("agent-contoso-support",),
        guardrail_identifier="gr-contoso-support",
        guardrail_version="DRAFT",
    ),
}


class PolicyStore:
    """Tenant policy store.

    Uses DynamoDB when POLICY_TABLE_NAME is configured and boto3 can initialize.
    Falls back to DEMO_POLICIES for local tests/examples.
    """

    def __init__(self, table_name: str | None = None) -> None:
        self.table_name = table_name or os.getenv("POLICY_TABLE_NAME")
        self._table = None
        if self.table_name:
            from ._aws import dynamodb_table

            self._table = dynamodb_table(self.table_name)

    def get_policy(self, tenant_id: str) -> TenantPolicy:
        if self._table is not None:
            response = self._table.get_item(Key={"tenant_id": tenant_id})
            item = response.get("Item")
            if not item:
                raise KeyError(f"no policy configured for tenant: {tenant_id}")
            return TenantPolicy.model_validate(_from_dynamodb_item(item))

        try:
            return DEMO_POLICIES[tenant_id]
        except KeyError as exc:
            raise KeyError(f"no policy configured for tenant: {tenant_id}") from exc


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
