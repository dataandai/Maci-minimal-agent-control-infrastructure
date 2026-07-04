from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import Field, ValidationError

from ..agent_registry import AgentRegistry, DEMO_AGENT_IDENTITIES
from ..audit import AuditEvent, AuditEventType, AuditLogger
from ..identity import MissingIdentityError, tenant_context_from_api_gateway_event
from ..kill_switch import KillSwitchRecord, KillSwitchScope, KillSwitchStore
from ..resource_ownership import DEMO_RESOURCE_OWNERSHIP, ResourceOwnershipStore
from ..schemas import AgentIdentity, ResourceOwnerRecord, StrictModel


class AdminActionInput(StrictModel):
    action: Literal[
        "upsert_agent",
        "revoke_agent",
        "upsert_resource_owner",
        "enable_kill_switch",
        "clear_kill_switch",
    ]
    agent: AgentIdentity | None = None
    resource_owner: ResourceOwnerRecord | None = None
    agent_id: str | None = None
    kill_scope: KillSwitchScope | None = None
    kill_key: str | None = None
    reason: str | None = Field(default=None, min_length=1, max_length=1000)


_audit = AuditLogger()
_agent_registry = AgentRegistry()
_resource_store = ResourceOwnershipStore()
_kill_switches = KillSwitchStore()


def lambda_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Small admin endpoint for local/dev control-plane operations.

    Production deployments should put this route behind a dedicated admin API,
    MFA, hardware-backed approval for sensitive actions, and change-management
    logging. The code here enforces role-gated admin access and performs the same
    strict schema checks as the runtime path.
    """

    try:
        tenant_context = tenant_context_from_api_gateway_event(event)
    except MissingIdentityError as exc:
        return _response(401, {"error": "missing_trusted_identity", "details": str(exc)})

    if "admin" not in tenant_context.roles:
        return _response(403, {"error": "admin_role_required"})

    try:
        body = event.get("body") or "{}"
        payload = json.loads(body) if isinstance(body, str) else body
        request = AdminActionInput.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        return _response(400, {"error": "invalid_admin_request", "details": str(exc)})

    try:
        result = _execute(request, actor_user_id=tenant_context.user_id, tenant_id=tenant_context.tenant_id)
    except ValueError as exc:
        return _response(400, {"error": "admin_action_failed", "details": str(exc)})

    _audit.emit(
        AuditEvent(
            request_id=tenant_context.request_id,
            tenant_id=tenant_context.tenant_id,
            event_type=AuditEventType.POLICY_ALLOWED,
            message=f"admin action executed: {request.action}",
            attributes={"action": request.action, "result": result},
        )
    )
    return _response(200, result)


def _execute(request: AdminActionInput, *, actor_user_id: str, tenant_id: str) -> dict[str, Any]:
    if request.action == "upsert_agent":
        if request.agent is None:
            raise ValueError("agent is required")
        if request.agent.tenant_id != tenant_id:
            raise ValueError("agent tenant must match authenticated admin tenant")
        _put_agent(request.agent)
        return {"ok": True, "agent_id": request.agent.agent_id}

    if request.action == "revoke_agent":
        if not request.agent_id:
            raise ValueError("agent_id is required")
        identity = _agent_registry.get_agent(request.agent_id)
        if identity.tenant_id != tenant_id:
            raise ValueError("cannot revoke agent from another tenant")
        revoked = identity.model_copy(update={"status": "revoked"})
        _put_agent(revoked)
        return {"ok": True, "agent_id": request.agent_id, "status": "revoked"}

    if request.action == "upsert_resource_owner":
        if request.resource_owner is None:
            raise ValueError("resource_owner is required")
        if request.resource_owner.tenant_id != tenant_id:
            raise ValueError("resource owner tenant must match authenticated admin tenant")
        _put_resource_owner(request.resource_owner)
        return {"ok": True, "resource_id": request.resource_owner.resource_id}

    if request.action == "enable_kill_switch":
        if request.kill_scope is None or not request.kill_key or not request.reason:
            raise ValueError("kill_scope, kill_key and reason are required")
        record = KillSwitchRecord(
            scope=request.kill_scope,
            key=request.kill_key,
            reason=request.reason,
            created_by=actor_user_id,
        )
        _kill_switches.set(record)
        return {"ok": True, "kill_switch": record.model_dump(mode="json")}

    if request.action == "clear_kill_switch":
        if request.kill_scope is None or not request.kill_key:
            raise ValueError("kill_scope and kill_key are required")
        _kill_switches.clear(request.kill_scope, request.kill_key)
        return {"ok": True, "cleared": {"scope": request.kill_scope.value, "key": request.kill_key}}

    raise ValueError("unsupported admin action")


def _put_agent(identity: AgentIdentity) -> None:
    table = getattr(_agent_registry, "_table", None)
    if table is not None:
        table.put_item(Item=identity.model_dump(mode="json"))
    else:
        DEMO_AGENT_IDENTITIES[identity.agent_id] = identity


def _put_resource_owner(owner: ResourceOwnerRecord) -> None:
    table = getattr(_resource_store, "_table", None)
    if table is not None:
        table.put_item(Item=owner.model_dump(mode="json"))
    else:
        DEMO_RESOURCE_OWNERSHIP[owner.resource_id] = owner


def _response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {"statusCode": status_code, "headers": {"content-type": "application/json"}, "body": json.dumps(body, sort_keys=True)}
