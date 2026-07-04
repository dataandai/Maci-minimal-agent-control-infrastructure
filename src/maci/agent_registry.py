from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

from .schemas import AgentIdentity, AgentStatus, ResourceAction, TenantContext, ToolName


class AgentIdentityError(PermissionError):
    """Raised when an agent identity is missing, revoked, suspended or over-privileged."""


DEMO_AGENT_IDENTITIES: dict[str, AgentIdentity] = {
    "agent-acme-support": AgentIdentity(
        agent_id="agent-acme-support",
        tenant_id="tenant-acme",
        owner_user_id="platform-owner",
        human_custodian="security@example.com",
        status=AgentStatus.ACTIVE,
        allowed_tools=(ToolName.CUSTOMER_LOOKUP.value, ToolName.TICKET_CREATION.value, ToolName.BILLING_CHECK.value),
        allowed_actions=(ResourceAction.READ_CUSTOMER, ResourceAction.CREATE_TICKET, ResourceAction.READ_BILLING),
    ),
    "agent-acme-billing-risk": AgentIdentity(
        agent_id="agent-acme-billing-risk",
        tenant_id="tenant-acme",
        owner_user_id="risk-owner",
        human_custodian="risk@example.com",
        status=AgentStatus.ACTIVE,
        allowed_tools=(ToolName.ACCOUNT_CREDIT.value, ToolName.BILLING_CHECK.value),
        allowed_actions=(ResourceAction.READ_BILLING, ResourceAction.ISSUE_CREDIT),
    ),
    "agent-contoso-support": AgentIdentity(
        agent_id="agent-contoso-support",
        tenant_id="tenant-contoso",
        owner_user_id="platform-owner",
        human_custodian="security@example.com",
        status=AgentStatus.ACTIVE,
        allowed_tools=(ToolName.CUSTOMER_LOOKUP.value,),
        allowed_actions=(ResourceAction.READ_CUSTOMER,),
    ),
}


class AgentRegistry:
    """First-class agent identity registry.

    Production deployments should persist agent identities in DynamoDB or an IAM/NHI
    identity system. The local fallback deliberately models agent passports instead
    of relying on anonymous Bedrock Agent invocations.
    """

    def __init__(self, table_name: str | None = None) -> None:
        self.table_name = table_name or os.getenv("AGENT_REGISTRY_TABLE_NAME")
        self._table = None
        if self.table_name:
            try:
                import boto3  # type: ignore

                self._table = boto3.resource("dynamodb").Table(self.table_name)
            except Exception:
                self._table = None

    def get_agent(self, agent_id: str) -> AgentIdentity:
        if self._table is not None:
            response = self._table.get_item(Key={"agent_id": agent_id})
            item = response.get("Item")
            if not item:
                raise AgentIdentityError(f"unknown agent identity: {agent_id}")
            return AgentIdentity.model_validate(_from_dynamodb_item(item))
        try:
            return DEMO_AGENT_IDENTITIES[agent_id]
        except KeyError as exc:
            raise AgentIdentityError(f"unknown agent identity: {agent_id}") from exc

    def ensure_active_agent_for_operation(
        self,
        tenant_context: TenantContext,
        tool_name: ToolName,
        action: ResourceAction,
        *,
        require_agent_id: bool | None = None,
    ) -> AgentIdentity | None:
        """Authorize the calling agent passport when present.

        Local direct tool tests may omit agent_id. Production can set
        REQUIRE_AGENT_ID=true to force every Bedrock action-group call to carry an
        agent identity in sessionAttributes.
        """

        require_agent = require_agent_id if require_agent_id is not None else os.getenv("REQUIRE_AGENT_ID", "false").lower() == "true"
        if not tenant_context.agent_id:
            if require_agent:
                raise AgentIdentityError("missing agent_id in trusted sessionAttributes")
            return None

        identity = self.get_agent(tenant_context.agent_id)
        if identity.tenant_id != tenant_context.tenant_id:
            raise AgentIdentityError("agent identity tenant does not match session tenant")
        if identity.status != AgentStatus.ACTIVE:
            raise AgentIdentityError(f"agent identity is not active: {identity.status.value}")
        if tool_name.value not in identity.allowed_tools:
            raise AgentIdentityError(f"agent is not allowed to use tool: {tool_name.value}")
        if identity.allowed_actions and action not in identity.allowed_actions:
            raise AgentIdentityError(f"agent is not allowed to perform action: {action.value}")
        return identity


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
