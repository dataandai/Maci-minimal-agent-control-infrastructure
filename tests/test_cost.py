from maci.cost import CostEstimator
from maci.policy_engine import PolicyEngine
from maci.policy_store import DEMO_POLICIES
from maci.schemas import GovernedRequest, TaskType, TenantContext


def test_cost_estimator_uses_tokens_not_flat_request_fee():
    estimator = CostEstimator()
    small = estimator.estimate_usage_cost("amazon.nova-lite-v1:0", 100, 100)
    large = estimator.estimate_usage_cost("amazon.nova-lite-v1:0", 10_000, 10_000)
    assert large.estimated_cost_usd > small.estimated_cost_usd


def test_policy_budget_precheck_uses_model_and_token_estimate():
    policy = DEMO_POLICIES["tenant-contoso"].model_copy(update={"current_month_spend_usd": 99.9998})
    request = GovernedRequest(
        tenant_context=TenantContext(tenant_id="tenant-contoso", user_id="u-1"),
        task_type=TaskType.SUPPORT_ANSWER,
        input="x" * 7000,
        requested_model="amazon.nova-lite-v1:0",
        max_output_tokens=1024,
    )
    decision = PolicyEngine().evaluate(request, policy)
    assert decision.decision == "deny"
    assert "budget" in decision.reason
