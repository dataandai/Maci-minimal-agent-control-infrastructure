from __future__ import annotations

from .agent_registry import AgentIdentityError, AgentRegistry
from .policy_store import PolicyStore
from .kill_switch import KillSwitchBlocked, KillSwitchStore
from .schemas import ResourceAction, TenantContext, ToolName


class ToolSecurityError(PermissionError):
    """Raised when a tool invocation violates tenant or agent policy."""


def enforce_tool_allowed(
    tenant_context: TenantContext,
    tool_name: ToolName,
    policy_store: PolicyStore | None = None,
    *,
    action: ResourceAction | None = None,
    agent_registry: AgentRegistry | None = None,
) -> None:
    """Authorize a Bedrock Agent tool invocation against tenant and agent policy."""

    try:
        KillSwitchStore().enforce(tenant_context, tool_name=tool_name.value)
    except KillSwitchBlocked as exc:
        raise ToolSecurityError(str(exc)) from exc

    store = policy_store or PolicyStore()
    try:
        policy = store.get_policy(tenant_context.tenant_id)
    except KeyError as exc:
        raise ToolSecurityError(f"unknown tenant: {tenant_context.tenant_id}") from exc

    if tool_name.value not in policy.allowed_tools:
        raise ToolSecurityError(f"tool not allowlisted for tenant: {tool_name.value}")

    if policy.allowed_agent_ids and tenant_context.agent_id and tenant_context.agent_id not in policy.allowed_agent_ids:
        raise ToolSecurityError(f"agent not allowlisted for tenant: {tenant_context.agent_id}")

    if action is not None and policy.allowed_resource_actions and action not in policy.allowed_resource_actions:
        raise ToolSecurityError(f"resource action not allowlisted for tenant: {action.value}")

    registry = agent_registry or AgentRegistry()
    if action is not None:
        try:
            registry.ensure_active_agent_for_operation(tenant_context, tool_name, action)
        except AgentIdentityError as exc:
            raise ToolSecurityError(str(exc)) from exc
