from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from ...approval import ApprovalError, ApprovalStore
from ...audit import AuditEvent, AuditEventType, AuditLogger
from ...authorization import AuthorizationError, ResourceAuthorizer
from ...bedrock_agent_event import BedrockAgentEventError, extract_model_parameters
from ...bedrock_agent_response import bedrock_function_response
from ...identity import MissingIdentityError, tenant_context_from_bedrock_agent_event
from ...guardrails import GuardrailChecker, GuardrailIntervention
from ...metrics import emit_metric
from ...schemas import AccountCreditInput, AccountCreditOutput, ResourceAction, RiskLevel, ToolName
from ...tool_security import ToolSecurityError, enforce_tool_allowed

_audit = AuditLogger()
_authorizer = ResourceAuthorizer()
_guardrails = GuardrailChecker()
_approvals = ApprovalStore()


def lambda_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """High-risk billing credit tool: always requires human approval."""

    try:
        tenant_context = tenant_context_from_bedrock_agent_event(event)
    except MissingIdentityError as exc:
        return bedrock_function_response(event, 401, {"error": "missing_trusted_session", "details": str(exc)}, response_state="FAILURE")
    try:
        enforce_tool_allowed(tenant_context, ToolName.ACCOUNT_CREDIT, action=ResourceAction.ISSUE_CREDIT)
    except ToolSecurityError as exc:
        return bedrock_function_response(event, 403, {"error": "tool_not_allowed", "details": str(exc)}, response_state="FAILURE")
    try:
        payload = extract_model_parameters(event)
        _guardrails.enforce_payload(tenant_context=tenant_context, step="tool_input", payload=payload)
        request = AccountCreditInput.model_validate(payload)
        _authorizer.enforce_customer_action(
            tenant_context,
            tool_name=ToolName.ACCOUNT_CREDIT,
            customer_id=request.customer_id,
            action=ResourceAction.ISSUE_CREDIT,
            risk_level=RiskLevel.HIGH,
            payload=request.model_dump(mode="json", exclude={"approval_id"}),
        )
    except (json.JSONDecodeError, BedrockAgentEventError, ValidationError, GuardrailIntervention) as exc:
        return bedrock_function_response(event, 400, {"error": "invalid_tool_input", "details": str(exc)}, response_state="REPROMPT")
    except AuthorizationError as exc:
        return bedrock_function_response(event, 403, {"error": "resource_not_allowed", "details": str(exc)}, response_state="FAILURE")

    if not request.approval_id:
        approval = _approvals.create_pending(
            tenant_context,
            tool_name=ToolName.ACCOUNT_CREDIT,
            resource_id=request.customer_id,
            action=ResourceAction.ISSUE_CREDIT,
            risk_level=RiskLevel.HIGH,
            payload=request.model_dump(mode="json", exclude={"approval_id"}),
        )
        _audit.emit(AuditEvent(request_id=tenant_context.request_id, tenant_id=tenant_context.tenant_id, event_type=AuditEventType.APPROVAL_REQUESTED, message="account credit requires human approval", attributes=approval.model_dump(mode="json")))
        result = AccountCreditOutput(tenant_id=tenant_context.tenant_id, customer_id=request.customer_id, amount_usd=request.amount_usd, status="pending_approval", approval_id=approval.approval_id, executed=False)
        return bedrock_function_response(event, 202, result.model_dump(mode="json"), response_state="REPROMPT")

    try:
        approval = _approvals.ensure_approved(
            tenant_context.tenant_id,
            request.approval_id,
            expected_action=ResourceAction.ISSUE_CREDIT,
            expected_resource_id=request.customer_id,
            expected_payload=request.model_dump(mode="json", exclude={"approval_id"}),
        )
    except ApprovalError as exc:
        return bedrock_function_response(event, 403, {"error": "approval_not_valid", "details": str(exc)}, response_state="FAILURE")

    result = AccountCreditOutput(tenant_id=tenant_context.tenant_id, customer_id=request.customer_id, amount_usd=request.amount_usd, status="executed", approval_id=approval.approval_id, executed=True)
    _audit.emit(AuditEvent(request_id=tenant_context.request_id, tenant_id=tenant_context.tenant_id, event_type=AuditEventType.TOOL_INVOKED, message="account_credit executed after approval", attributes={"customer_id": request.customer_id, "approval_id": approval.approval_id, "amount_usd": request.amount_usd}))
    emit_metric("HighRiskToolExecuted", 1, dimensions={"tenant_id": tenant_context.tenant_id, "tool": ToolName.ACCOUNT_CREDIT.value})
    return bedrock_function_response(event, 200, result.model_dump(mode="json"))
