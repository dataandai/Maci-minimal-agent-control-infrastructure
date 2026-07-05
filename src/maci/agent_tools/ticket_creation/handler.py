from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from ...audit import AuditEvent, AuditEventType, AuditLogger
from ...conversation import ConversationStore
from ...authorization import AuthorizationError, ResourceAuthorizer
from ...bedrock_agent_event import BedrockAgentEventError, extract_model_parameters
from ...bedrock_agent_response import bedrock_function_response
from ...identity import MissingIdentityError, tenant_context_from_bedrock_agent_event
from ...guardrails import GuardrailChecker, GuardrailIntervention
from ...idempotency import TicketStore, deterministic_ticket_key
from ...metrics import emit_metric
from ...recovery import WorkflowStateStore, WorkflowStatus
from ...schemas import ResourceAction, RiskLevel, TicketCreationInput, TicketCreationOutput, ToolName
from ...tool_security import ToolSecurityError, enforce_tool_allowed

_audit = AuditLogger()
_ticket_store = TicketStore()
_authorizer = ResourceAuthorizer()
_guardrails = GuardrailChecker()
_conversation_store = ConversationStore()
_workflow_state_store = WorkflowStateStore()


def lambda_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Bedrock Agent action-group compatible ticket creation tool."""

    try:
        tenant_context = tenant_context_from_bedrock_agent_event(event)
    except MissingIdentityError as exc:
        return bedrock_function_response(event, 401, {"error": "missing_trusted_session", "details": str(exc)}, response_state="FAILURE")

    try:
        enforce_tool_allowed(tenant_context, ToolName.TICKET_CREATION, action=ResourceAction.CREATE_TICKET)
    except ToolSecurityError as exc:
        _audit.emit(AuditEvent(request_id=tenant_context.request_id, tenant_id=tenant_context.tenant_id, event_type=AuditEventType.POLICY_DENIED, message="ticket_creation denied", attributes={"reason": str(exc)}))
        emit_metric("ToolDenied", 1, dimensions={"tenant_id": tenant_context.tenant_id, "tool": ToolName.TICKET_CREATION.value})
        return bedrock_function_response(event, 403, {"error": "tool_not_allowed", "details": str(exc)}, response_state="FAILURE")

    try:
        payload = extract_model_parameters(event)
        _guardrails.enforce_payload(tenant_context=tenant_context, step="tool_input", payload=payload)
        request = TicketCreationInput.model_validate(payload)
        _authorizer.enforce_customer_action(
            tenant_context,
            tool_name=ToolName.TICKET_CREATION,
            customer_id=request.customer_id,
            action=ResourceAction.CREATE_TICKET,
            risk_level=RiskLevel.MEDIUM,
            payload=request.model_dump(mode="json"),
        )
    except (json.JSONDecodeError, BedrockAgentEventError, ValidationError, GuardrailIntervention) as exc:
        emit_metric("ToolSchemaValidationFailed", 1, dimensions={"tenant_id": tenant_context.tenant_id, "tool": ToolName.TICKET_CREATION.value})
        return bedrock_function_response(event, 400, {"error": "invalid_tool_input", "details": str(exc)}, response_state="REPROMPT")
    except AuthorizationError as exc:
        _audit.emit(AuditEvent(request_id=tenant_context.request_id, tenant_id=tenant_context.tenant_id, event_type=AuditEventType.POLICY_DENIED, message="ticket_creation resource denied", attributes={"customer_id": payload.get("customer_id"), "reason": str(exc)}))
        emit_metric("ToolResourceDenied", 1, dimensions={"tenant_id": tenant_context.tenant_id, "tool": ToolName.TICKET_CREATION.value})
        return bedrock_function_response(event, 403, {"error": "resource_not_allowed", "details": str(exc)}, response_state="FAILURE")

    ticket_key = deterministic_ticket_key(
        tenant_id=tenant_context.tenant_id,
        customer_id=request.customer_id,
        title=request.title,
        description=request.description,
        request_id=tenant_context.request_id,
    )
    proposed_ticket_id = f"TCK-{uuid4().hex[:10].upper()}"
    ticket_id, created = _ticket_store.create_or_get(
        tenant_id=tenant_context.tenant_id,
        ticket_key=ticket_key,
        ticket_id=proposed_ticket_id,
        payload=request.model_dump(mode="json"),
    )
    result = TicketCreationOutput(
        tenant_id=tenant_context.tenant_id,
        ticket_id=ticket_id,
        priority=request.priority,
        created=created,
    )
    _workflow_state_store.transition(
        tenant_context,
        conversation_id=_conversation_id(tenant_context),
        status=WorkflowStatus.TICKET_CREATED,
        idempotency_key=ticket_key,
        metadata={"tool": ToolName.TICKET_CREATION.value, "customer_id": request.customer_id, "ticket_id": ticket_id, "created": created},
    )
    _conversation_store.append_tool_result_summary(
        tenant_context,
        _conversation_id(tenant_context),
        ToolName.TICKET_CREATION.value,
        {"customer_id": request.customer_id, "ticket_id": ticket_id, "created": created},
    )
    _audit.emit(AuditEvent(request_id=tenant_context.request_id, tenant_id=tenant_context.tenant_id, event_type=AuditEventType.TOOL_INVOKED, message="ticket_creation invoked", attributes={"customer_id": request.customer_id, "ticket_id": ticket_id, "created": created, "agent_id": tenant_context.agent_id}))
    emit_metric("ToolInvoked", 1, dimensions={"tenant_id": tenant_context.tenant_id, "tool": ToolName.TICKET_CREATION.value})
    return bedrock_function_response(event, 200, result.model_dump(mode="json"))


def _conversation_id(tenant_context):
    return tenant_context.conversation_id or f"conv-{tenant_context.request_id}"
