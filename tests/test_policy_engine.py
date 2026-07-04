import pytest

from maci.cost import CostEstimator
from maci.policy_engine import PolicyEngine
from maci.schemas import (
    AgentRequest,
    PolicyDecision,
    TaskType,
    TenantContext,
    TenantPolicy,
)


def _context() -> TenantContext:
    return TenantContext(tenant_id="tenant-acme", user_id="u-1")


def _policy() -> TenantPolicy:
    return TenantPolicy(
        tenant_id="tenant-acme",
        allowed_models=("model-a",),
        allowed_knowledge_base_ids=("kb-acme",),
        allowed_tools=("customer_lookup",),
        max_input_chars=1000,
        max_output_tokens=2048,
        monthly_budget_usd=10,
        current_month_spend_usd=0,
    )


def _governed(request: AgentRequest):
    return PolicyEngine().bind_request(request, _context())


def test_policy_allows_expected_request():
    request = AgentRequest(
        tenant_id="tenant-acme",
        user_id="u-1",
        task_type=TaskType.RAG,
        input="answer from docs",
        requested_model="model-a",
        requested_knowledge_base_id="kb-acme",
        requested_tools=("customer_lookup",),
    )
    decision = PolicyEngine().evaluate(_governed(request), _policy())
    assert decision.decision == PolicyDecision.ALLOW


def test_policy_rejects_body_tenant_impersonation_before_policy_eval():
    request = AgentRequest(
        tenant_id="tenant-other",
        user_id="u-1",
        task_type=TaskType.RAG,
        input="answer from docs",
        requested_model="model-a",
    )
    with pytest.raises(ValueError, match="tenant_id"):
        PolicyEngine().bind_request(request, _context())


def test_policy_denies_cross_tenant_knowledge_base():
    request = AgentRequest(
        tenant_id="tenant-acme",
        user_id="u-1",
        task_type=TaskType.RAG,
        input="answer from docs",
        requested_model="model-a",
        requested_knowledge_base_id="kb-other-tenant",
    )
    decision = PolicyEngine().evaluate(_governed(request), _policy())
    assert decision.decision == PolicyDecision.DENY
    assert "knowledge base" in decision.reason


def test_policy_denies_unapproved_tool():
    request = AgentRequest(
        tenant_id="tenant-acme",
        user_id="u-1",
        task_type=TaskType.TOOL_ACTION,
        input="issue a refund",
        requested_model="model-a",
        requested_tools=("billing_refund",),
    )
    decision = PolicyEngine().evaluate(_governed(request), _policy())
    assert decision.decision == PolicyDecision.DENY
    assert "tools" in decision.reason


def test_policy_denies_budget_exceeded():
    policy = _policy().model_copy(update={"current_month_spend_usd": 9.99, "monthly_budget_usd": 10.0})
    request = AgentRequest(
        tenant_id="tenant-acme",
        user_id="u-1",
        task_type=TaskType.SUPPORT_ANSWER,
        input="hello",
        requested_model="model-a",
    )
    estimator = CostEstimator(pricing_per_1k_tokens={"model-a": (10.0, 10.0)})
    decision = PolicyEngine(cost_estimator=estimator).evaluate(_governed(request), policy)
    assert decision.decision == PolicyDecision.DENY
    assert "budget" in decision.reason
