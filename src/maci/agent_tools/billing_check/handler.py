from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from ...audit import AuditEvent, AuditEventType, AuditLogger
from ...conversation import ConversationStore
from ...authorization import AuthorizationError, ResourceAuthorizer
from ...bedrock_agent_event import BedrockAgentEventError, extract_model_parameters
from ...bedrock_agent_response import bedrock_function_response
from ...identity import MissingIdentityError, tenant_context_from_bedrock_agent_event
from ...guardrails import GuardrailChecker, GuardrailIntervention
from ...metrics import emit_metric
from ...recovery import WorkflowStateStore, WorkflowStatus
from ...schemas import BillingCheckInput, BillingCheckOutput, ResourceAction, RiskLevel, ToolName
from ...tool_security import ToolSecurityError, enforce_tool_allowed

_audit = AuditLogger()
_authorizer = ResourceAuthorizer()
_guardrails = GuardrailChecker()
_conversation_store = ConversationStore()
_workflow_state_store = WorkflowStateStore()


def lambda_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    try:
        tenant_context = tenant_context_from_bedrock_agent_event(event)
    except MissingIdentityError as exc:
        return bedrock_function_response(event, 401, {"error": "missing_trusted_session", "details": str(exc)}, response_state="FAILURE")
    try:
        enforce_tool_allowed(tenant_context, ToolName.BILLING_CHECK, action=ResourceAction.READ_BILLING)
    except ToolSecurityError as exc:
        _audit.emit(AuditEvent(request_id=tenant_context.request_id, tenant_id=tenant_context.tenant_id, event_type=AuditEventType.POLICY_DENIED, message="billing_check denied", attributes={"reason": str(exc)}))
        emit_metric("ToolDenied", 1, dimensions={"tenant_id": tenant_context.tenant_id, "tool": ToolName.BILLING_CHECK.value})
        return bedrock_function_response(event, 403, {"error": "tool_not_allowed", "details": str(exc)}, response_state="FAILURE")
    try:
        payload = extract_model_parameters(event)
        _guardrails.enforce_payload(tenant_context=tenant_context, step="tool_input", payload=payload)
        request = BillingCheckInput.model_validate(payload)
        _authorizer.enforce_customer_action(
            tenant_context,
            tool_name=ToolName.BILLING_CHECK,
            customer_id=request.customer_id,
            action=ResourceAction.READ_BILLING,
            risk_level=RiskLevel.MEDIUM,
            payload=request.model_dump(mode="json"),
        )
    except (json.JSONDecodeError, BedrockAgentEventError, ValidationError, GuardrailIntervention) as exc:
        return bedrock_function_response(event, 400, {"error": "invalid_tool_input", "details": str(exc)}, response_state="REPROMPT")
    except AuthorizationError as exc:
        _audit.emit(AuditEvent(request_id=tenant_context.request_id, tenant_id=tenant_context.tenant_id, event_type=AuditEventType.POLICY_DENIED, message="billing_check resource denied", attributes={"customer_id": payload.get("customer_id"), "reason": str(exc)}))
        emit_metric("ToolResourceDenied", 1, dimensions={"tenant_id": tenant_context.tenant_id, "tool": ToolName.BILLING_CHECK.value})
        return bedrock_function_response(event, 403, {"error": "resource_not_allowed", "details": str(exc)}, response_state="FAILURE")
    result = BillingCheckOutput(
        tenant_id=tenant_context.tenant_id,
        customer_id=request.customer_id,
        account_status="current",
        outstanding_balance_usd=0.0,
        last_invoice_id="inv-demo-001",
    )
    _workflow_state_store.transition(
        tenant_context,
        conversation_id=_conversation_id(tenant_context),
        status=WorkflowStatus.BILLING_CHECK_DONE,
        metadata={"tool": ToolName.BILLING_CHECK.value, "customer_id": request.customer_id, "account_status": result.account_status},
    )
    _conversation_store.append_tool_result_summary(
        tenant_context,
        _conversation_id(tenant_context),
        ToolName.BILLING_CHECK.value,
        {"customer_id": request.customer_id, "account_status": result.account_status, "outstanding_balance_usd": result.outstanding_balance_usd},
    )
    _audit.emit(AuditEvent(request_id=tenant_context.request_id, tenant_id=tenant_context.tenant_id, event_type=AuditEventType.TOOL_INVOKED, message="billing_check invoked", attributes={"customer_id": request.customer_id}))
    emit_metric("ToolInvoked", 1, dimensions={"tenant_id": tenant_context.tenant_id, "tool": ToolName.BILLING_CHECK.value})
    return bedrock_function_response(event, 200, result.model_dump(mode="json"))


def _conversation_id(tenant_context):
    return tenant_context.conversation_id or f"conv-{tenant_context.request_id}"
