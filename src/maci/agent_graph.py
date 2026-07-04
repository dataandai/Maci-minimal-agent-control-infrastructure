from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field, ValidationError

from .guardrails import GuardrailChecker, GuardrailIntervention
from .observability import TraceRecorder
from .schemas import StrictModel, TenantContext


class GraphNode(str, Enum):
    ORCHESTRATOR = "orchestrator"
    PLANNER = "planner"
    RETRIEVAL = "retrieval"
    TOOL = "tool"
    RESPONSE_COMPOSER = "response_composer"
    VALIDATOR = "validator"
    FINAL = "final"
    CIRCUIT_BREAKER = "circuit_breaker"


class AgentGraphState(StrictModel):
    tenant_context: TenantContext
    input: str
    plan: tuple[str, ...] = Field(default_factory=tuple)
    retrieved_context: str | None = None
    tool_results: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    draft_response: dict[str, Any] = Field(default_factory=dict)
    final_response: dict[str, Any] | None = None
    validation_attempts: int = 0
    trace: dict[str, Any] = Field(default_factory=dict)


class StructuredAgentOutput(StrictModel):
    answer: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    cited_sources: tuple[str, ...] = Field(default_factory=tuple)
    tool_calls: tuple[str, ...] = Field(default_factory=tuple)


class DeterministicAgentGraph:
    """Small deterministic graph runtime for the architecture diagram.

    It is intentionally simple: nodes are normal Python functions, transitions
    are explicit, validation is Pydantic v2 strict, and repeated validation
    failures route to a circuit-breaker state instead of an infinite agent loop.
    """

    def __init__(self, guardrails: GuardrailChecker | None = None, max_validation_attempts: int = 3) -> None:
        self.guardrails = guardrails or GuardrailChecker()
        self.max_validation_attempts = max_validation_attempts

    def run(self, state: AgentGraphState) -> AgentGraphState:
        recorder = TraceRecorder()
        tc = state.tenant_context
        try:
            with recorder.span(GraphNode.ORCHESTRATOR.value, tc, gen_ai_system="bedrock-control-plane"):
                self.guardrails.enforce_text(tenant_context=tc, step="input", text=state.input)
            with recorder.span(GraphNode.PLANNER.value, tc):
                state = state.model_copy(update={"plan": self._plan(state.input)})
            with recorder.span(GraphNode.RETRIEVAL.value, tc):
                state = state.model_copy(update={"retrieved_context": "tenant-scoped context placeholder"})
            with recorder.span(GraphNode.TOOL.value, tc):
                state = state.model_copy(update={"tool_results": ({"tool": "policy_lookup", "ok": True},)})
            while state.validation_attempts < self.max_validation_attempts:
                with recorder.span(GraphNode.RESPONSE_COMPOSER.value, tc, attempt=state.validation_attempts + 1):
                    state = state.model_copy(update={"draft_response": self._compose(state)})
                with recorder.span(GraphNode.VALIDATOR.value, tc, attempt=state.validation_attempts + 1):
                    try:
                        final = StructuredAgentOutput.model_validate(state.draft_response)
                        state = state.model_copy(update={"final_response": final.model_dump(mode="json"), "trace": recorder.as_trace_payload()})
                        return state
                    except ValidationError:
                        state = state.model_copy(update={"validation_attempts": state.validation_attempts + 1})
            with recorder.span(GraphNode.CIRCUIT_BREAKER.value, tc, reason="validation_failed"):
                state = state.model_copy(
                    update={
                        "final_response": {"error": "validation_failed", "safe_stop": True},
                        "trace": recorder.as_trace_payload(),
                    }
                )
                return state
        except GuardrailIntervention as exc:
            with recorder.span(GraphNode.CIRCUIT_BREAKER.value, tc, reason=exc.result.reason):
                return state.model_copy(
                    update={
                        "final_response": {"error": "guardrail_intervened", "safe_stop": True, "findings": exc.result.findings},
                        "trace": recorder.as_trace_payload(),
                    }
                )

    @staticmethod
    def _plan(input_text: str) -> tuple[str, ...]:
        if "ticket" in input_text.lower():
            return ("retrieve_context", "select_tool", "compose_response", "validate")
        return ("retrieve_context", "compose_response", "validate")

    @staticmethod
    def _compose(state: AgentGraphState) -> dict[str, Any]:
        return {
            "answer": "Governed response composed from tenant-scoped context and validated tool results.",
            "confidence": 0.82,
            "cited_sources": ("tenant_kb",) if state.retrieved_context else (),
            "tool_calls": tuple(str(item.get("tool")) for item in state.tool_results if item.get("tool")),
        }
