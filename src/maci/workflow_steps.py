from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from .bedrock_gateway import BedrockGateway
from .schemas import BedrockInvocationRequest, TenantContext, WorkflowInvocationRequest

_gateway = BedrockGateway()


def validate_workflow_input(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Validate Step Functions workflow input and return a normalized payload."""

    try:
        request = WorkflowInvocationRequest.model_validate(event)
    except ValidationError as exc:
        return {"ok": False, "error": "invalid_workflow_input", "details": str(exc), "input": event}
    return {"ok": True, "request": request.model_dump(mode="json")}


def invoke_bedrock_step(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Invoke Bedrock from Step Functions after deterministic validation."""

    if not event.get("ok"):
        return event
    request = WorkflowInvocationRequest.model_validate(event["request"])
    tenant_context = TenantContext(
        tenant_id=request.tenant_id,
        user_id=request.user_id,
        request_id=request.request_id,
    )
    response = _gateway.invoke(
        BedrockInvocationRequest(
            tenant_context=tenant_context,
            model_id=request.model_id,
            prompt=request.input,
            max_output_tokens=request.max_output_tokens,
            guardrail_identifier=request.guardrail_identifier,
            guardrail_version=request.guardrail_version,
        )
    )
    return {"ok": True, "request": event["request"], "bedrock": response.model_dump(mode="json")}


def finalize_workflow(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Return a small, stable workflow result."""

    if not event.get("ok"):
        return event
    bedrock = event.get("bedrock", {})
    return {
        "ok": True,
        "answer": bedrock.get("output_text", ""),
        "model_id": bedrock.get("model_id"),
        "input_tokens": bedrock.get("input_tokens", 0),
        "output_tokens": bedrock.get("output_tokens", 0),
    }
