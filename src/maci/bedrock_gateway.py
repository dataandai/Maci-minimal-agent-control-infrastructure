from __future__ import annotations

import os
from typing import Any

from .schemas import (
    BedrockAgentInvocationRequest,
    BedrockAgentInvocationResponse,
    BedrockInvocationRequest,
    BedrockInvocationResponse,
    BedrockRetrieveRequest,
    BedrockRetrieveResponse,
)


class BedrockGateway:
    """Boundary around Amazon Bedrock calls.

    Default mode is deterministic local_stub so tests and examples run without
    AWS credentials. Set ENABLE_REAL_BEDROCK=true in AWS to call Bedrock Runtime
    and Bedrock Agent Runtime through boto3.
    """

    def __init__(self, enable_real_bedrock: bool | None = None) -> None:
        self.enable_real_bedrock = enable_real_bedrock if enable_real_bedrock is not None else os.getenv("ENABLE_REAL_BEDROCK", "false").lower() == "true"
        self._runtime_client = None
        self._agent_runtime_client = None
        if self.enable_real_bedrock:
            import boto3  # type: ignore

            self._runtime_client = boto3.client("bedrock-runtime")
            self._agent_runtime_client = boto3.client("bedrock-agent-runtime")

    def invoke(self, request: BedrockInvocationRequest) -> BedrockInvocationResponse:
        if self.enable_real_bedrock and self._runtime_client is not None:
            return self._invoke_converse(request)
        return BedrockInvocationResponse(
            model_id=request.model_id,
            output_text=(
                "This is a governed Bedrock response placeholder. "
                "In production this would be returned by Amazon Bedrock after policy checks."
            ),
            input_tokens=max(1, len(request.prompt.split())),
            output_tokens=20,
            raw={
                "mode": "local_stub",
                "guardrail_identifier": request.guardrail_identifier,
                "guardrail_version": request.guardrail_version,
            },
        )

    def invoke_agent(self, request: BedrockAgentInvocationRequest) -> BedrockAgentInvocationResponse:
        """Invoke a real Bedrock Agent alias with trusted session attributes.

        This is intentionally separate from direct model invocation because the
        security boundary is different: all tenant/user identity is injected as
        sessionAttributes and must never be elicited from model parameters.
        """

        if self.enable_real_bedrock and self._agent_runtime_client is not None:
            response = self._agent_runtime_client.invoke_agent(
                agentId=request.agent_id,
                agentAliasId=request.agent_alias_id,
                sessionId=request.session_id,
                inputText=request.input_text,
                enableTrace=request.enable_trace,
                sessionState={
                    "sessionAttributes": {
                        "tenant_id": request.tenant_context.tenant_id,
                        "user_id": request.tenant_context.user_id,
                        "request_id": request.tenant_context.request_id,
                        "roles": " ".join(request.tenant_context.roles),
                    }
                },
            )
            chunks: list[str] = []
            raw_events: list[Any] = []
            for event in response.get("completion", []):
                raw_events.append(_json_safe(event))
                chunk = event.get("chunk") if isinstance(event, dict) else None
                if isinstance(chunk, dict) and "bytes" in chunk:
                    data = chunk["bytes"]
                    if isinstance(data, bytes):
                        chunks.append(data.decode("utf-8", errors="replace"))
                    else:
                        chunks.append(str(data))
            return BedrockAgentInvocationResponse(
                agent_id=request.agent_id,
                agent_alias_id=request.agent_alias_id,
                output_text="".join(chunks).strip(),
                raw={"events": raw_events},
            )
        return BedrockAgentInvocationResponse(
            agent_id=request.agent_id,
            agent_alias_id=request.agent_alias_id,
            output_text="This is a governed Bedrock Agent placeholder response with trusted sessionAttributes.",
            raw={"mode": "local_stub"},
        )

    def retrieve(self, request: BedrockRetrieveRequest) -> BedrockRetrieveResponse:
        if self.enable_real_bedrock and self._agent_runtime_client is not None:
            kwargs: dict[str, Any] = {
                "knowledgeBaseId": request.knowledge_base_id,
                "retrievalQuery": {"text": request.query},
                "retrievalConfiguration": {
                    "vectorSearchConfiguration": {
                        "numberOfResults": request.number_of_results,
                        "filter": {"equals": {"key": "tenant_id", "value": request.tenant_context.tenant_id}},
                    }
                },
            }
            if request.guardrail_identifier and request.guardrail_version:
                kwargs["guardrailConfiguration"] = {
                    "guardrailId": request.guardrail_identifier,
                    "guardrailVersion": request.guardrail_version,
                }
            response = self._agent_runtime_client.retrieve(**kwargs)
            results = response.get("retrievalResults", [])
            retrieved_text = "\n\n".join(
                str(item.get("content", {}).get("text", "")) for item in results if isinstance(item, dict)
            ).strip()
            return BedrockRetrieveResponse(
                knowledge_base_id=request.knowledge_base_id,
                retrieved_text=retrieved_text,
                source_count=len(results),
                raw=_json_safe(response),
            )
        return BedrockRetrieveResponse(
            knowledge_base_id=request.knowledge_base_id,
            retrieved_text="Tenant-scoped retrieval placeholder from an allowlisted Bedrock Knowledge Base.",
            source_count=1,
            raw={
                "mode": "local_stub",
                "tenant_filter": request.tenant_context.tenant_id,
                "guardrail_identifier": request.guardrail_identifier,
                "guardrail_version": request.guardrail_version,
            },
        )

    def _invoke_converse(self, request: BedrockInvocationRequest) -> BedrockInvocationResponse:
        kwargs: dict[str, Any] = {
            "modelId": request.model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": request.prompt}],
                }
            ],
            "inferenceConfig": {"maxTokens": request.max_output_tokens},
        }
        if request.guardrail_identifier and request.guardrail_version:
            kwargs["guardrailConfig"] = {
                "guardrailIdentifier": request.guardrail_identifier,
                "guardrailVersion": request.guardrail_version,
            }
        response = self._runtime_client.converse(**kwargs)  # type: ignore[union-attr]
        output = response.get("output", {}).get("message", {}).get("content", [])
        output_text = "".join(str(part.get("text", "")) for part in output if isinstance(part, dict))
        usage = response.get("usage", {})
        return BedrockInvocationResponse(
            model_id=request.model_id,
            output_text=output_text,
            input_tokens=int(usage.get("inputTokens", 0)),
            output_tokens=int(usage.get("outputTokens", 0)),
            raw=_json_safe(response),
        )


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
