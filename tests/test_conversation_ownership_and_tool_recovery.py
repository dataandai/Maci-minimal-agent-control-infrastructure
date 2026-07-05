import json

from maci.agent_tools.account_credit import handler as account_credit_handler
from maci.agent_tools.billing_check import handler as billing_check_handler
from maci.agent_tools.customer_lookup import handler as customer_lookup_handler
from maci.agent_tools.ticket_creation import handler as ticket_creation_handler
from maci.approval_review.handler import lambda_handler as approval_review
from maci.policy_engine import PolicyEngine
from maci.recovery import WorkflowStatus
from maci.request_router import conversation_store, lambda_handler as router_handler
from maci.schemas import AgentRequest, TaskType, TenantContext


def _api_event(body: dict, *, tenant_id: str = "tenant-acme", user_id: str = "u-1", conversation_id_claim: str | None = None):
    claims = {
        "custom:tenant_id": tenant_id,
        "sub": user_id,
        "cognito:groups": "support-agent",
    }
    if conversation_id_claim:
        claims["custom:conversation_id"] = conversation_id_claim
    return {
        "requestContext": {"authorizer": {"jwt": {"claims": claims}}},
        "body": json.dumps(body),
    }


def _bedrock_event(
    parameters: dict,
    *,
    request_id: str,
    conversation_id: str,
    tenant_id: str = "tenant-acme",
    user_id: str = "u-1",
    agent_id: str = "agent-acme-support",
):
    return {
        "sessionAttributes": {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "request_id": request_id,
            "agent_id": agent_id,
            "conversation_id": conversation_id,
        },
        "parameters": [{"name": key, "type": "string", "value": value} for key, value in parameters.items()],
    }


def _approval_api_event(approval_id: str, *, tenant_id: str = "tenant-acme"):
    return {
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {
                        "custom:tenant_id": tenant_id,
                        "sub": "risk-approver-1",
                        "cognito:groups": "risk-approver",
                    }
                }
            }
        },
        "body": json.dumps({"approval_id": approval_id, "decision": "approve", "reason": "verified in recovery regression test"}),
    }


def test_same_tenant_user_cannot_resume_another_users_conversation():
    conversation_id = "conv-ownership-regression"
    first = router_handler(
        _api_event(
            {
                "tenant_id": "tenant-acme",
                "user_id": "u-alice",
                "task_type": TaskType.SUPPORT_ANSWER,
                "input": "Start a private support conversation.",
                "requested_model": "anthropic.claude-3-5-sonnet-20241022-v2:0",
                "conversation_id": conversation_id,
            },
            user_id="u-alice",
        )
    )
    assert first["statusCode"] == 200
    assert conversation_store.get("tenant-acme", conversation_id).created_by_user_id == "u-alice"

    second = router_handler(
        _api_event(
            {
                "tenant_id": "tenant-acme",
                "user_id": "u-mallory",
                "task_type": TaskType.SUPPORT_ANSWER,
                "input": "Append to Alice conversation.",
                "requested_model": "anthropic.claude-3-5-sonnet-20241022-v2:0",
                "conversation_id": conversation_id,
            },
            user_id="u-mallory",
        )
    )
    assert second["statusCode"] == 403
    assert "conversation" in json.loads(second["body"])["reason"]


def test_body_conversation_id_cannot_override_trusted_conversation_claim():
    request = AgentRequest(
        task_type=TaskType.SUPPORT_ANSWER,
        input="hello",
        conversation_id="conv-body",
    )
    ctx = TenantContext(tenant_id="tenant-acme", user_id="u-1", conversation_id="conv-trusted")
    try:
        PolicyEngine().bind_request(request, ctx)
    except ValueError as exc:
        assert "conversation_id" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("body conversation_id must not override trusted context")


def test_tool_handlers_write_real_workflow_status_transitions():
    conv_id = "conv-tool-status-regression"

    customer_resp = customer_lookup_handler.lambda_handler(
        _bedrock_event(
            {"customer_id": "cust-123", "reason": "routine support check"},
            request_id="wf-customer-status",
            conversation_id=conv_id,
        )
    )
    assert customer_resp["statusCode"] == 200
    assert customer_lookup_handler._workflow_state_store.get("tenant-acme", "wf-customer-status").status == WorkflowStatus.CUSTOMER_LOOKUP_DONE

    billing_resp = billing_check_handler.lambda_handler(
        _bedrock_event(
            {"customer_id": "cust-123", "reason": "routine billing check"},
            request_id="wf-billing-status",
            conversation_id=conv_id,
        )
    )
    assert billing_resp["statusCode"] == 200
    assert billing_check_handler._workflow_state_store.get("tenant-acme", "wf-billing-status").status == WorkflowStatus.BILLING_CHECK_DONE

    ticket_resp = ticket_creation_handler.lambda_handler(
        _bedrock_event(
            {
                "customer_id": "cust-123",
                "title": "Billing discrepancy",
                "description": "Customer reports a possible invoice overcharge.",
                "priority": "high",
            },
            request_id="wf-ticket-status",
            conversation_id=conv_id,
        )
    )
    assert ticket_resp["statusCode"] == 200
    ticket_record = ticket_creation_handler._workflow_state_store.get("tenant-acme", "wf-ticket-status")
    assert ticket_record.status == WorkflowStatus.TICKET_CREATED
    assert ticket_record.idempotency_key

    pending_resp = account_credit_handler.lambda_handler(
        _bedrock_event(
            {"customer_id": "cust-123", "amount_usd": 25.0, "reason": "billing goodwill adjustment"},
            request_id="wf-credit-status",
            conversation_id=conv_id,
            agent_id="agent-acme-billing-risk",
        )
    )
    assert pending_resp["statusCode"] == 202
    approval_id = json.loads(pending_resp["body"])["approval_id"]
    pending_record = account_credit_handler._workflow_state_store.get("tenant-acme", "wf-credit-status")
    assert pending_record.status == WorkflowStatus.WAITING_FOR_APPROVAL
    assert pending_record.approval_id == approval_id

    assert approval_review(_approval_api_event(approval_id))["statusCode"] == 200
    executed_resp = account_credit_handler.lambda_handler(
        _bedrock_event(
            {
                "customer_id": "cust-123",
                "amount_usd": 25.0,
                "reason": "billing goodwill adjustment",
                "approval_id": approval_id,
            },
            request_id="wf-credit-status",
            conversation_id=conv_id,
            agent_id="agent-acme-billing-risk",
        )
    )
    assert executed_resp["statusCode"] == 200
    executed_record = account_credit_handler._workflow_state_store.get("tenant-acme", "wf-credit-status")
    assert executed_record.status == WorkflowStatus.CREDIT_EXECUTED
    assert executed_record.idempotency_key
