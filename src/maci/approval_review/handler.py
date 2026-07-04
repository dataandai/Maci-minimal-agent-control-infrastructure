from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import Field, ValidationError

from ..approval import ApprovalError, ApprovalStore
from ..audit import AuditEvent, AuditEventType, AuditLogger
from ..identity import MissingIdentityError, tenant_context_from_api_gateway_event
from ..schemas import StrictModel


class ApprovalDecisionInput(StrictModel):
    approval_id: str = Field(min_length=1)
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=3, max_length=1000)


_store = ApprovalStore()
_audit = AuditLogger()


def lambda_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Human approval endpoint for high-risk agent actions.

    Requires a trusted JWT role `risk-approver` or `admin`. This is the software
    approval boundary; production deployments can additionally require hardware
    backed MFA at the IdP level before issuing the approver token.
    """

    try:
        tenant_context = tenant_context_from_api_gateway_event(event)
    except MissingIdentityError as exc:
        return _response(401, {"error": "missing_trusted_identity", "details": str(exc)})

    if not ({"risk-approver", "admin"} & set(tenant_context.roles)):
        return _response(403, {"error": "approver_role_required"})

    try:
        body = event.get("body") or "{}"
        payload = json.loads(body) if isinstance(body, str) else body
        request = ApprovalDecisionInput.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        return _response(400, {"error": "invalid_approval_decision", "details": str(exc)})

    try:
        if request.decision == "approve":
            record = _store.approve(
                tenant_context.tenant_id,
                request.approval_id,
                decided_by_user_id=tenant_context.user_id,
                reason=request.reason,
            )
        else:
            record = _store.reject(
                tenant_context.tenant_id,
                request.approval_id,
                decided_by_user_id=tenant_context.user_id,
                reason=request.reason,
            )
    except ApprovalError as exc:
        return _response(404, {"error": "approval_not_found", "details": str(exc)})

    _audit.emit(
        AuditEvent(
            request_id=tenant_context.request_id,
            tenant_id=tenant_context.tenant_id,
            event_type=AuditEventType.APPROVAL_DECIDED,
            message=f"approval {request.decision}d",
            attributes=record.model_dump(mode="json"),
        )
    )
    return _response(200, record.model_dump(mode="json"))


def _response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {"statusCode": status_code, "headers": {"content-type": "application/json"}, "body": json.dumps(body, sort_keys=True)}
