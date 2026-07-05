from __future__ import annotations

import json
import os
from typing import Any

from pydantic import ValidationError

from .audit import AuditEvent, AuditEventType, AuditLogger
from .bedrock_gateway import BedrockGateway
from .circuit_breaker import FailureCategory, TenantCircuitBreaker
from .conversation import ConversationStatus, ConversationStore
from .cost import CostEstimator, UsageLedger, UsageLedgerEvent
from .guardrails import GuardrailChecker, GuardrailIntervention
from .identity import MissingIdentityError, tenant_context_from_api_gateway_event
from .kill_switch import KillSwitchBlocked, KillSwitchStore
from .metrics import emit_metric
from .model_router import ModelRouter
from .observability import TraceRecorder
from .policy_engine import PolicyEngine, PolicyViolation
from .policy_store import PolicyStore
from .recovery import WorkflowStateStore, WorkflowStatus
from .schemas import (
    AgentRequest,
    AgentResponse,
    BedrockAgentInvocationRequest,
    BedrockInvocationRequest,
    BedrockRetrieveRequest,
    TaskType,
    WorkflowInvocationRequest,
)


def _dynamodb_table_from_env(env_name: str):
    table_name = os.getenv(env_name)
    if not table_name:
        return None
    try:
        import boto3  # type: ignore

        return boto3.resource("dynamodb").Table(table_name)
    except Exception:
        return None


audit_logger = AuditLogger()
policy_store = PolicyStore()
policy_engine = PolicyEngine()
bedrock_gateway = BedrockGateway()
cost_estimator = CostEstimator()
model_router = ModelRouter(default_model_id=policy_engine.default_model_id)
guardrails = GuardrailChecker()
kill_switches = KillSwitchStore()
usage_ledger = UsageLedger()
circuit_breaker = TenantCircuitBreaker(
    threshold=int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "3")),
    open_seconds=int(os.getenv("CIRCUIT_BREAKER_OPEN_SECONDS", "300")),
    table=_dynamodb_table_from_env("CIRCUIT_BREAKER_TABLE_NAME"),
)
conversation_store = ConversationStore()
workflow_state_store = WorkflowStateStore()


def lambda_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """API Gateway compatible Lambda handler.

    This is the deterministic boundary before Bedrock: it extracts trusted
    identity, validates schema, enforces tenant policy, optionally performs
    tenant-scoped retrieval, and then invokes either direct Bedrock Converse or a
    Bedrock Agent alias with sessionAttributes.
    """

    try:
        tenant_context = tenant_context_from_api_gateway_event(event)
    except MissingIdentityError as exc:
        return _response(401, {"error": "missing_trusted_identity", "details": str(exc)})

    trace_recorder = TraceRecorder()

    try:
        kill_switches.enforce(tenant_context)
    except KillSwitchBlocked as exc:
        audit_logger.emit(
            AuditEvent(
                request_id=tenant_context.request_id,
                tenant_id=tenant_context.tenant_id,
                event_type=AuditEventType.CIRCUIT_BREAKER_TRIPPED,
                message=str(exc),
                attributes=exc.record.model_dump(mode="json"),
            )
        )
        return _response(423, {"error": "kill_switch_active", "details": str(exc), "record": exc.record.model_dump(mode="json")})

    if circuit_breaker.is_open(tenant_context.tenant_id, FailureCategory.TENANT_BUDGET_EXCEEDED):
        return _response(429, {"error": "tenant_circuit_open", "category": FailureCategory.TENANT_BUDGET_EXCEEDED.value})

    try:
        body = event.get("body") or "{}"
        payload = json.loads(body) if isinstance(body, str) else body
        request = AgentRequest.model_validate(payload)
        if _has_redteam_override(request) and not _redteam_overrides_enabled():
            return _response(400, {"error": "redteam_overrides_disabled", "details": "redteam override fields are test-only and require ENABLE_REDTEAM_OVERRIDES=true"})
        governed_request = policy_engine.bind_request(request, tenant_context)
        conversation = conversation_store.start_or_resume(tenant_context, conversation_id=request.conversation_id)
        tenant_context = tenant_context.model_copy(update={"conversation_id": conversation.conversation_id})
        governed_request = governed_request.model_copy(update={"tenant_context": tenant_context, "conversation_id": conversation.conversation_id})
        conversation_store.append_user_message(tenant_context, conversation.conversation_id, request.input)
        workflow_state_store.transition(tenant_context, conversation_id=conversation.conversation_id, status=WorkflowStatus.IDENTITY_BOUND)
    except (json.JSONDecodeError, ValidationError) as exc:
        circuit_breaker.record_failure(tenant_context.tenant_id, FailureCategory.SCHEMA_VALIDATION_FAILED)
        emit_metric("SchemaValidationFailed", 1, dimensions={"tenant_id": tenant_context.tenant_id})
        return _response(400, {"error": "invalid_request_schema", "details": str(exc)})
    except ValueError as exc:
        circuit_breaker.record_failure(tenant_context.tenant_id, FailureCategory.UNKNOWN)
        audit_logger.emit(
            AuditEvent(
                request_id=tenant_context.request_id,
                tenant_id=tenant_context.tenant_id,
                event_type=AuditEventType.POLICY_DENIED,
                message=str(exc),
                attributes={"reason": "identity_mismatch"},
            )
        )
        emit_metric("IdentityMismatch", 1, dimensions={"tenant_id": tenant_context.tenant_id})
        return _response(403, {"error": "identity_mismatch", "reason": str(exc)})

    audit_logger.emit(
        AuditEvent(
            request_id=tenant_context.request_id,
            tenant_id=tenant_context.tenant_id,
            event_type=AuditEventType.REQUEST_RECEIVED,
            message="request received by router",
            attributes={"task_type": request.task_type.value, "conversation_id": conversation.conversation_id},
        )
    )
    workflow_state_store.transition(tenant_context, conversation_id=conversation.conversation_id, status=WorkflowStatus.RECEIVED)

    try:
        policy = policy_store.get_policy(tenant_context.tenant_id)
        routed_model = model_router.choose_model(
            task_type=governed_request.task_type,
            requested_model=governed_request.requested_model,
            policy=policy,
            input_chars=len(governed_request.input),
        )
        governed_request = governed_request.model_copy(update={"requested_model": routed_model})
        with trace_recorder.span("policy.evaluate", tenant_context, model_id=routed_model, task_type=governed_request.task_type.value):
            guardrails.enforce_text(
                tenant_context=tenant_context,
                step="user_input",
                text=governed_request.input,
                guardrail_identifier=policy.guardrail_identifier,
                guardrail_version=policy.guardrail_version,
            )
            decision = policy_engine.enforce(governed_request, policy)
            workflow_state_store.transition(tenant_context, conversation_id=conversation.conversation_id, status=WorkflowStatus.GUARDRAIL_PASSED)
    except KeyError as exc:
        circuit_breaker.record_failure(tenant_context.tenant_id, FailureCategory.UNKNOWN)
        return _response(403, {"error": "unknown_tenant", "details": str(exc)})
    except GuardrailIntervention as exc:
        circuit_breaker.record_failure(tenant_context.tenant_id, FailureCategory.GUARDRAIL_INTERVENED)
        audit_logger.emit(
            AuditEvent(
                request_id=tenant_context.request_id,
                tenant_id=tenant_context.tenant_id,
                event_type=AuditEventType.GUARDRAIL_INTERVENED,
                message=exc.result.reason,
                attributes=exc.result.model_dump(mode="json"),
            )
        )
        emit_metric("GuardrailIntervened", 1, dimensions={"tenant_id": tenant_context.tenant_id, "step": exc.result.step})
        conversation_store.append_system_status(tenant_context, conversation.conversation_id, {"error": "guardrail_intervened", "reason": exc.result.reason})
        conversation_store.update_status(tenant_context.tenant_id, conversation.conversation_id, ConversationStatus.FAILED_SAFE)
        workflow_state_store.transition(tenant_context, conversation_id=conversation.conversation_id, status=WorkflowStatus.FAILED_SAFE, last_error=exc.result.reason)
        return _response(400, {"error": "guardrail_intervened", "reason": exc.result.reason, "findings": exc.result.findings, "conversation_id": conversation.conversation_id})
    except PolicyViolation as exc:
        category = _policy_violation_to_category(exc.reason)
        circuit_breaker.record_failure(tenant_context.tenant_id, category)
        audit_logger.emit(
            AuditEvent(
                request_id=tenant_context.request_id,
                tenant_id=tenant_context.tenant_id,
                event_type=AuditEventType.POLICY_DENIED,
                message=exc.reason,
                attributes=exc.decision.model_dump(mode="json"),
            )
        )
        emit_metric("PolicyDenied", 1, dimensions={"tenant_id": tenant_context.tenant_id, "category": category.value})
        conversation_store.append_system_status(tenant_context, conversation.conversation_id, {"error": "policy_denied", "reason": exc.reason})
        conversation_store.update_status(tenant_context.tenant_id, conversation.conversation_id, ConversationStatus.FAILED_SAFE)
        workflow_state_store.transition(tenant_context, conversation_id=conversation.conversation_id, status=WorkflowStatus.FAILED_SAFE, last_error=exc.reason)
        return _response(403, {"error": "policy_denied", "reason": exc.reason, "conversation_id": conversation.conversation_id})

    audit_logger.emit(
        AuditEvent(
            request_id=tenant_context.request_id,
            tenant_id=tenant_context.tenant_id,
            event_type=AuditEventType.POLICY_ALLOWED,
            message="tenant policy allowed request",
            attributes={**decision.model_dump(mode="json"), "conversation_id": conversation.conversation_id},
        )
    )
    workflow_state_store.transition(tenant_context, conversation_id=conversation.conversation_id, status=WorkflowStatus.POLICY_CHECKED)

    mode = "direct"
    prompt = request.input
    retrieval_trace: dict[str, Any] = {}
    try:
        if request.task_type == TaskType.RAG and request.requested_knowledge_base_id:
            mode = "rag"
            with trace_recorder.span("bedrock.retrieve", tenant_context, knowledge_base_id=request.requested_knowledge_base_id):
                if request.redteam_context_override is not None:
                    retrieved_text = request.redteam_context_override
                    retrieval_trace = {"source_count": 1, "redteam_context_override": True}
                else:
                    retrieve_response = bedrock_gateway.retrieve(
                        BedrockRetrieveRequest(
                            tenant_context=tenant_context,
                            knowledge_base_id=request.requested_knowledge_base_id,
                            query=request.input,
                            guardrail_identifier=policy.guardrail_identifier,
                            guardrail_version=policy.guardrail_version,
                        )
                    )
                    retrieved_text = retrieve_response.retrieved_text
                    retrieval_trace = {"source_count": retrieve_response.source_count}
                guardrails.enforce_text(
                    tenant_context=tenant_context,
                    step="retrieved_context",
                    text=retrieved_text,
                    guardrail_identifier=policy.guardrail_identifier,
                    guardrail_version=policy.guardrail_version,
                )
            prompt = f"Use the tenant-scoped retrieved context below.\n\nContext:\n{retrieved_text}\n\nUser question:\n{request.input}"
            audit_logger.emit(
                AuditEvent(
                    request_id=tenant_context.request_id,
                    tenant_id=tenant_context.tenant_id,
                    event_type=AuditEventType.KNOWLEDGE_BASE_RETRIEVED,
                    message="tenant knowledge base retrieved",
                    attributes={"knowledge_base_id": request.requested_knowledge_base_id, **retrieval_trace},
                )
            )

        if request.redteam_tool_output_override is not None:
            tool_payload = request.redteam_tool_output_override
            if not isinstance(tool_payload, dict):
                tool_payload = {"tool_output": str(tool_payload)}
            with trace_recorder.span("guardrail.tool_output", tenant_context):
                guardrails.enforce_payload(
                    tenant_context=tenant_context,
                    step="tool_output",
                    payload=tool_payload,
                    guardrail_identifier=policy.guardrail_identifier,
                    guardrail_version=policy.guardrail_version,
                )
    except GuardrailIntervention as exc:
        circuit_breaker.record_failure(tenant_context.tenant_id, FailureCategory.GUARDRAIL_INTERVENED)
        audit_logger.emit(
            AuditEvent(
                request_id=tenant_context.request_id,
                tenant_id=tenant_context.tenant_id,
                event_type=AuditEventType.GUARDRAIL_INTERVENED,
                message=exc.result.reason,
                attributes=exc.result.model_dump(mode="json"),
            )
        )
        emit_metric("GuardrailIntervened", 1, dimensions={"tenant_id": tenant_context.tenant_id, "step": exc.result.step})
        conversation_store.append_system_status(tenant_context, conversation.conversation_id, {"error": "guardrail_intervened", "reason": exc.result.reason})
        conversation_store.update_status(tenant_context.tenant_id, conversation.conversation_id, ConversationStatus.FAILED_SAFE)
        workflow_state_store.transition(tenant_context, conversation_id=conversation.conversation_id, status=WorkflowStatus.FAILED_SAFE, last_error=exc.result.reason)
        return _response(400, {"error": "guardrail_intervened", "reason": exc.result.reason, "findings": exc.result.findings, "conversation_id": conversation.conversation_id})

    workflow_arn = os.getenv("WORKFLOW_STATE_MACHINE_ARN")
    agent_id = os.getenv("BEDROCK_AGENT_ID")
    agent_alias_id = os.getenv("BEDROCK_AGENT_ALIAS_ID")
    use_agent = os.getenv("ENABLE_BEDROCK_AGENT", "false").lower() == "true" and agent_id and agent_alias_id
    workflow_state_store.transition(tenant_context, conversation_id=conversation.conversation_id, status=WorkflowStatus.PLANNING_STARTED)

    if request.task_type == TaskType.WORKFLOW and workflow_arn:
        mode = "workflow"
        workflow_result = _start_sync_workflow(
            workflow_arn,
            WorkflowInvocationRequest(
                request_id=tenant_context.request_id,
                tenant_id=tenant_context.tenant_id,
                user_id=tenant_context.user_id,
                input=prompt,
                model_id=decision.model_id or policy_engine.default_model_id,
                max_output_tokens=request.max_output_tokens,
                guardrail_identifier=policy.guardrail_identifier,
                guardrail_version=policy.guardrail_version,
            ),
        )
        answer = str(workflow_result.get("answer", ""))
        model_id = str(workflow_result.get("model_id") or decision.model_id or policy_engine.default_model_id)
        input_tokens = int(workflow_result.get("input_tokens", max(1, len(prompt.split()))))
        output_tokens = int(workflow_result.get("output_tokens", max(1, len(answer.split()))))
        raw_trace = {"workflow": workflow_result}
    elif use_agent:
        mode = "agent"
        agent_response = bedrock_gateway.invoke_agent(
            BedrockAgentInvocationRequest(
                tenant_context=tenant_context,
                agent_id=agent_id,
                agent_alias_id=agent_alias_id,
                session_id=tenant_context.request_id,
                input_text=prompt,
            )
        )
        answer = agent_response.output_text
        model_id = decision.model_id or policy_engine.default_model_id
        input_tokens = max(1, len(prompt.split()))
        output_tokens = max(1, len(answer.split()))
        raw_trace = agent_response.raw
    else:
        invocation = BedrockInvocationRequest(
            tenant_context=tenant_context,
            model_id=decision.model_id or policy_engine.default_model_id,
            prompt=prompt,
            max_output_tokens=request.max_output_tokens,
            guardrail_identifier=policy.guardrail_identifier,
            guardrail_version=policy.guardrail_version,
        )
        with trace_recorder.span("bedrock.invoke", tenant_context, model_id=invocation.model_id):
            bedrock_response = bedrock_gateway.invoke(invocation)
        answer = bedrock_response.output_text
        model_id = bedrock_response.model_id
        input_tokens = bedrock_response.input_tokens
        output_tokens = bedrock_response.output_tokens
        raw_trace = bedrock_response.raw

    try:
        with trace_recorder.span("guardrail.output", tenant_context, model_id=model_id):
            guardrails.enforce_text(
                tenant_context=tenant_context,
                step="model_output",
                text=answer,
                guardrail_identifier=policy.guardrail_identifier,
                guardrail_version=policy.guardrail_version,
            )
    except GuardrailIntervention as exc:
        circuit_breaker.record_failure(tenant_context.tenant_id, FailureCategory.GUARDRAIL_INTERVENED)
        audit_logger.emit(AuditEvent(request_id=tenant_context.request_id, tenant_id=tenant_context.tenant_id, event_type=AuditEventType.GUARDRAIL_INTERVENED, message=exc.result.reason, attributes=exc.result.model_dump(mode="json")))
        conversation_store.append_system_status(tenant_context, conversation.conversation_id, {"error": "output_guardrail_intervened", "reason": exc.result.reason})
        conversation_store.update_status(tenant_context.tenant_id, conversation.conversation_id, ConversationStatus.FAILED_SAFE)
        workflow_state_store.transition(tenant_context, conversation_id=conversation.conversation_id, status=WorkflowStatus.FAILED_SAFE, last_error=exc.result.reason)
        return _response(400, {"error": "guardrail_intervened", "reason": exc.result.reason, "conversation_id": conversation.conversation_id})

    circuit_breaker.record_success(tenant_context.tenant_id, FailureCategory.BEDROCK_THROTTLED)

    cost = cost_estimator.estimate_usage_cost(model_id, input_tokens, output_tokens)
    usage_ledger.record(
        UsageLedgerEvent(
            request_id=tenant_context.request_id,
            tenant_id=tenant_context.tenant_id,
            user_id=tenant_context.user_id,
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=cost.estimated_cost_usd,
        )
    )
    emit_metric("EstimatedCostUsd", cost.estimated_cost_usd, unit="None", dimensions={"tenant_id": tenant_context.tenant_id, "model_id": model_id})

    audit_logger.emit(
        AuditEvent(
            request_id=tenant_context.request_id,
            tenant_id=tenant_context.tenant_id,
            event_type=AuditEventType.MODEL_INVOKED,
            message="bedrock gateway invoked",
            attributes={
                "mode": mode,
                "model_id": model_id,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "guardrail_identifier": policy.guardrail_identifier,
                "estimated_cost_usd": cost.estimated_cost_usd,
                "pricing_source": cost.pricing_source,
            },
        )
    )

    conversation_store.append_assistant_message(tenant_context, conversation.conversation_id, answer)
    conversation_store.update_status(tenant_context.tenant_id, conversation.conversation_id, ConversationStatus.COMPLETED)
    workflow_state_store.transition(tenant_context, conversation_id=conversation.conversation_id, status=WorkflowStatus.FINAL_RESPONSE_SENT)

    response = AgentResponse(
        request_id=tenant_context.request_id,
        tenant_id=tenant_context.tenant_id,
        conversation_id=conversation.conversation_id,
        answer=answer,
        model_id=model_id,
        tool_calls=request.requested_tools,
        knowledge_base_id=request.requested_knowledge_base_id,
        policy_decision_id=decision.decision_id,
        circuit_breaker_open=circuit_breaker.is_open(tenant_context.tenant_id),
        mode=mode,
        trace={"retrieval": retrieval_trace, "bedrock": raw_trace, "otel": trace_recorder.as_trace_payload()},
    )
    return _response(200, response.model_dump(mode="json"))



def _has_redteam_override(request: AgentRequest) -> bool:
    return request.redteam_context_override is not None or request.redteam_tool_output_override is not None


def _redteam_overrides_enabled() -> bool:
    return os.getenv("ENABLE_REDTEAM_OVERRIDES", "false").lower() in {"1", "true", "yes", "on"}

def _start_sync_workflow(state_machine_arn: str, workflow_request: WorkflowInvocationRequest) -> dict[str, Any]:
    try:
        import boto3  # type: ignore

        client = boto3.client("stepfunctions")
        response = client.start_sync_execution(
            stateMachineArn=state_machine_arn,
            name=workflow_request.request_id[:80].replace(":", "-"),
            input=json.dumps(workflow_request.model_dump(mode="json")),
        )
        output = response.get("output") or "{}"
        parsed = json.loads(output) if isinstance(output, str) else output
        if not isinstance(parsed, dict):
            return {"ok": False, "error": "invalid_workflow_output", "raw": parsed}
        return parsed
    except Exception as exc:
        return {"ok": False, "error": "workflow_invocation_failed", "details": str(exc)}


def _policy_violation_to_category(reason: str) -> FailureCategory:
    if "model" in reason:
        return FailureCategory.MODEL_NOT_ALLOWED
    if "tools" in reason:
        return FailureCategory.TOOL_NOT_ALLOWED
    if "knowledge base" in reason:
        return FailureCategory.KNOWLEDGE_BASE_DENIED
    if "budget" in reason:
        return FailureCategory.TENANT_BUDGET_EXCEEDED
    return FailureCategory.UNKNOWN


def _response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body, sort_keys=True),
    }
