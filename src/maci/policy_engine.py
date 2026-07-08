from __future__ import annotations

from dataclasses import dataclass, field

from .cost import CostEstimator
from .schemas import (
    AgentRequest,
    GovernedRequest,
    PolicyDecision,
    PolicyDecisionRecord,
    TenantContext,
    TenantPolicy,
)


class PolicyViolation(Exception):
    """Raised when a request violates deterministic tenant policy."""

    def __init__(self, reason: str, decision: PolicyDecisionRecord):
        super().__init__(reason)
        self.reason = reason
        self.decision = decision


@dataclass(frozen=True)
class PolicyEngine:
    """Deterministic policy engine. No model-controlled security decisions."""

    default_model_id: str = "anthropic.claude-sonnet-5"
    cost_estimator: CostEstimator = field(default_factory=CostEstimator)

    def bind_request(self, request: AgentRequest, tenant_context: TenantContext) -> GovernedRequest:
        """Bind untrusted request intent to trusted infrastructure identity.

        The client body may contain tenant_id/user_id as backwards-compatible
        echo fields, but they are treated as claims to verify, never as identity.
        """

        if request.tenant_id is not None and request.tenant_id != tenant_context.tenant_id:
            raise ValueError("request tenant_id does not match authenticated tenant claim")
        if request.user_id is not None and request.user_id != tenant_context.user_id:
            raise ValueError("request user_id does not match authenticated subject claim")
        if (
            request.conversation_id is not None
            and tenant_context.conversation_id is not None
            and request.conversation_id != tenant_context.conversation_id
        ):
            raise ValueError("request conversation_id does not match authenticated conversation claim")

        return GovernedRequest(
            tenant_context=tenant_context,
            task_type=request.task_type,
            input=request.input,
            requested_model=request.requested_model,
            requested_knowledge_base_id=request.requested_knowledge_base_id,
            requested_tools=request.requested_tools,
            max_output_tokens=request.max_output_tokens,
            conversation_id=request.conversation_id,
        )

    def evaluate(self, request: GovernedRequest, policy: TenantPolicy) -> PolicyDecisionRecord:
        model_id = request.requested_model or self.default_model_id
        tenant_id = request.tenant_context.tenant_id

        if tenant_id != policy.tenant_id:
            return self._deny(tenant_id, "authenticated tenant does not match policy tenant", model_id)

        if len(request.input) > policy.max_input_chars:
            return self._deny(tenant_id, "input exceeds tenant max_input_chars", model_id)

        if model_id not in policy.allowed_models:
            return self._deny(tenant_id, f"model not allowlisted: {model_id}", model_id)

        if request.max_output_tokens > policy.max_output_tokens:
            return self._deny(tenant_id, "requested max_output_tokens exceeds tenant policy", model_id)

        if request.requested_knowledge_base_id:
            if request.requested_knowledge_base_id not in policy.allowed_knowledge_base_ids:
                return self._deny(
                    tenant_id,
                    f"knowledge base not allowlisted: {request.requested_knowledge_base_id}",
                    model_id,
                    knowledge_base_id=request.requested_knowledge_base_id,
                )

        denied_tools = [tool for tool in request.requested_tools if tool not in policy.allowed_tools]
        if denied_tools:
            return self._deny(
                tenant_id,
                f"tools not allowlisted: {', '.join(denied_tools)}",
                model_id,
                tools=request.requested_tools,
            )

        estimated_cost = self.cost_estimator.estimate_request_cost(
            model_id=model_id,
            input_chars=len(request.input),
            max_output_tokens=request.max_output_tokens,
        ).estimated_cost_usd

        if policy.current_month_spend_usd + estimated_cost > policy.monthly_budget_usd:
            return self._deny(tenant_id, "tenant monthly budget would be exceeded", model_id)

        return PolicyDecisionRecord(
            tenant_id=tenant_id,
            decision=PolicyDecision.ALLOW,
            reason="request satisfies tenant policy",
            model_id=model_id,
            knowledge_base_id=request.requested_knowledge_base_id,
            tools=request.requested_tools,
        )

    def enforce(self, request: GovernedRequest, policy: TenantPolicy) -> PolicyDecisionRecord:
        decision = self.evaluate(request, policy)
        if decision.decision == PolicyDecision.DENY:
            raise PolicyViolation(decision.reason, decision)
        return decision

    @staticmethod
    def _deny(
        tenant_id: str,
        reason: str,
        model_id: str | None = None,
        knowledge_base_id: str | None = None,
        tools: tuple[str, ...] = (),
    ) -> PolicyDecisionRecord:
        return PolicyDecisionRecord(
            tenant_id=tenant_id,
            decision=PolicyDecision.DENY,
            reason=reason,
            model_id=model_id,
            knowledge_base_id=knowledge_base_id,
            tools=tools,
        )
