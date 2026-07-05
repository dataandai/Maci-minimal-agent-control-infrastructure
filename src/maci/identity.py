from __future__ import annotations

from typing import Any
from uuid import uuid4

from .schemas import TenantContext


class MissingIdentityError(ValueError):
    """Raised when trusted infrastructure identity claims are absent."""


TENANT_CLAIM_KEYS = (
    "tenant_id",
    "custom:tenant_id",
    "https://example.com/tenant_id",
)
USER_CLAIM_KEYS = (
    "sub",
    "user_id",
    "username",
    "cognito:username",
)
ROLE_CLAIM_KEYS = (
    "roles",
    "custom:roles",
    "cognito:groups",
)


def tenant_context_from_api_gateway_event(event: dict[str, Any]) -> TenantContext:
    """Extract trusted tenant context from API Gateway authorizer claims.

    Supports both HTTP API JWT authorizers (requestContext.authorizer.jwt.claims)
    and simple custom authorizer output (requestContext.authorizer.<claim>).
    """

    authorizer = event.get("requestContext", {}).get("authorizer", {}) or {}
    claims = authorizer.get("jwt", {}).get("claims", {}) or {}
    merged_claims = {**authorizer, **claims}

    tenant_id = _first_present(merged_claims, TENANT_CLAIM_KEYS)
    user_id = _first_present(merged_claims, USER_CLAIM_KEYS)
    if not tenant_id or not user_id:
        raise MissingIdentityError("missing trusted tenant/user claims in requestContext.authorizer")

    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        roles=_roles_from_claims(merged_claims),
        agent_id=_first_present(merged_claims, ("agent_id", "custom:agent_id")),
        conversation_id=_first_present(merged_claims, ("conversation_id", "custom:conversation_id")),
    )


def tenant_context_from_bedrock_agent_event(event: dict[str, Any]) -> TenantContext:
    """Extract trusted tenant context from Bedrock Agent sessionAttributes.

    Model-controlled parameters/requestBody are intentionally ignored for
    identity. Bedrock sessionAttributes should be injected by the application
    when it calls InvokeAgent after authentication.
    """

    session_attributes = event.get("sessionAttributes") or {}
    prompt_session_attributes = event.get("promptSessionAttributes") or {}
    merged = {**prompt_session_attributes, **session_attributes}

    tenant_id = _first_present(merged, TENANT_CLAIM_KEYS)
    user_id = _first_present(merged, USER_CLAIM_KEYS)
    if not tenant_id or not user_id:
        raise MissingIdentityError("missing tenant/user in Bedrock Agent sessionAttributes")

    agent = event.get("agent") if isinstance(event.get("agent"), dict) else {}
    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        roles=_roles_from_claims(merged),
        request_id=merged.get("request_id") or str(uuid4()),
        agent_id=_first_present(merged, ("agent_id", "custom:agent_id")) or agent.get("id") or event.get("agentId"),
        conversation_id=_first_present(merged, ("conversation_id", "custom:conversation_id")),
    )


def _first_present(values: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = values.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return None


def _roles_from_claims(values: dict[str, Any]) -> tuple[str, ...]:
    for key in ROLE_CLAIM_KEYS:
        value = values.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            return tuple(role.strip() for role in value.replace(",", " ").split() if role.strip())
        if isinstance(value, list | tuple | set):
            return tuple(str(role) for role in value)
    return ()
