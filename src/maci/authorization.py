from __future__ import annotations

from .policy_store import PolicyStore
from .resource_ownership import ResourceOwnershipError, ResourceOwnershipStore
from .schemas import (
    OperationAuthorizationDecision,
    OperationAuthorizationRequest,
    ResourceAction,
    RiskLevel,
    TenantContext,
    ToolName,
)


class AuthorizationError(PermissionError):
    """Raised when a resource/action authorization check fails."""


class ResourceAuthorizer:
    """Per-operation authorization for tool calls.

    Tool allowlists answer "may this tenant use this capability?". This class
    answers the production question "may this user/agent perform this exact
    action on this exact resource?".
    """

    def __init__(self, policy_store: PolicyStore | None = None, ownership_store: ResourceOwnershipStore | None = None) -> None:
        self.policy_store = policy_store or PolicyStore()
        self.ownership_store = ownership_store or ResourceOwnershipStore()

    def authorize(self, request: OperationAuthorizationRequest) -> OperationAuthorizationDecision:
        try:
            policy = self.policy_store.get_policy(request.tenant_context.tenant_id)
        except KeyError:
            return OperationAuthorizationDecision(allowed=False, reason="unknown tenant")

        if request.tool_name.value not in policy.allowed_tools:
            return OperationAuthorizationDecision(allowed=False, reason=f"tool not allowlisted: {request.tool_name.value}")

        if policy.allowed_resource_actions and request.action not in policy.allowed_resource_actions:
            return OperationAuthorizationDecision(allowed=False, reason=f"action not allowlisted: {request.action.value}")

        if request.resource_id:
            try:
                owner = self.ownership_store.enforce_owned_by_tenant(request.tenant_context, request.resource_id)
            except ResourceOwnershipError as exc:
                return OperationAuthorizationDecision(allowed=False, reason=str(exc))

            # Local/dev fallback: if no explicit ownership record exists, optionally
            # allow legacy prefix-scoped demo IDs. Staging/prod should set
            # REQUIRE_RESOURCE_OWNERSHIP=true to fail closed instead.
            if owner is None and policy.allowed_customer_id_prefixes:
                if not any(request.resource_id.startswith(prefix) for prefix in policy.allowed_customer_id_prefixes):
                    return OperationAuthorizationDecision(
                        allowed=False,
                        reason="resource is outside tenant-scoped customer prefixes",
                    )

        approval_required = request.tool_name.value in policy.human_approval_required_tools or request.risk_level in {
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        }
        return OperationAuthorizationDecision(
            allowed=True,
            reason="operation authorized",
            approval_required=approval_required,
        )

    def enforce_customer_action(
        self,
        tenant_context: TenantContext,
        *,
        tool_name: ToolName,
        customer_id: str,
        action: ResourceAction,
        risk_level: RiskLevel = RiskLevel.LOW,
        payload: dict | None = None,
    ) -> OperationAuthorizationDecision:
        decision = self.authorize(
            OperationAuthorizationRequest(
                tenant_context=tenant_context,
                tool_name=tool_name,
                action=action,
                resource_id=customer_id,
                risk_level=risk_level,
                payload=payload or {},
            )
        )
        if not decision.allowed:
            raise AuthorizationError(decision.reason)
        return decision
