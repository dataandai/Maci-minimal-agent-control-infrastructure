import json

from maci.conversation import ConversationMessageType, ConversationStatus, ConversationStore
from maci.idempotency import OperationIdempotencyStore, deterministic_operation_key
from maci.recovery import RecoveryScanner, ResumePolicy, WorkflowStateStore, WorkflowStatus
from maci.request_router import conversation_store, lambda_handler, workflow_state_store
from maci.schemas import TaskType, TenantContext


def _event(body: dict, tenant_id: str = "tenant-acme", user_id: str = "u-1"):
    return {
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {
                        "custom:tenant_id": tenant_id,
                        "sub": user_id,
                        "cognito:groups": "support-agent",
                    }
                }
            }
        },
        "body": json.dumps(body),
    }


def test_conversation_store_separates_transcript_from_audit():
    ctx = TenantContext(tenant_id="tenant-acme", user_id="u-1", request_id="req-conv", agent_id="agent-acme-support")
    store = ConversationStore()
    record = store.start_or_resume(ctx, conversation_id="conv-demo")
    store.append_user_message(ctx, record.conversation_id, "Check billing for cust-123")
    store.append_assistant_message(ctx, record.conversation_id, "Credit request is pending approval.")
    store.update_status(ctx.tenant_id, record.conversation_id, ConversationStatus.WAITING_FOR_APPROVAL)

    messages = store.list_messages(ctx.tenant_id, record.conversation_id)
    assert [m.message_type for m in messages] == [ConversationMessageType.USER_MESSAGE, ConversationMessageType.ASSISTANT_MESSAGE]
    assert store.get(ctx.tenant_id, record.conversation_id).status == ConversationStatus.WAITING_FOR_APPROVAL


def test_router_persists_conversation_and_workflow_state():
    response = lambda_handler(
        _event(
            {
                "tenant_id": "tenant-acme",
                "user_id": "u-1",
                "task_type": TaskType.SUPPORT_ANSWER,
                "input": "How do I reset SSO settings?",
                "requested_model": "anthropic.claude-sonnet-5",
                "conversation_id": "conv-router-test",
            }
        )
    )
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["conversation_id"] == "conv-router-test"

    record = conversation_store.get("tenant-acme", "conv-router-test")
    assert record.status == ConversationStatus.COMPLETED
    messages = conversation_store.list_messages("tenant-acme", "conv-router-test")
    assert messages[0].message_type == ConversationMessageType.USER_MESSAGE
    assert messages[-1].message_type == ConversationMessageType.ASSISTANT_MESSAGE

    workflow_record = workflow_state_store.get("tenant-acme", body["request_id"])
    assert workflow_record.status == WorkflowStatus.FINAL_RESPONSE_SENT


def test_recovery_scanner_classifies_resume_safety():
    ctx = TenantContext(tenant_id="tenant-acme", user_id="u-1", request_id="wf-1")
    store = WorkflowStateStore()
    store.transition(ctx, conversation_id="conv-1", status=WorkflowStatus.PLANNING_STARTED)

    ctx_write = ctx.model_copy(update={"request_id": "wf-2"})
    store.transition(ctx_write, conversation_id="conv-2", status=WorkflowStatus.TICKET_CREATED, idempotency_key="ticket-key")

    ctx_approval = ctx.model_copy(update={"request_id": "wf-3"})
    store.transition(ctx_approval, conversation_id="conv-3", status=WorkflowStatus.WAITING_FOR_APPROVAL, approval_id="apr-123")

    decisions = {decision.workflow_id: decision for decision in RecoveryScanner(store).scan_tenant("tenant-acme")}
    assert decisions["wf-1"].resume_policy == ResumePolicy.AUTO_RESUME
    assert decisions["wf-2"].resume_policy == ResumePolicy.IDEMPOTENT_RESUME
    assert decisions["wf-3"].resume_policy == ResumePolicy.HUMAN_REVIEW_REQUIRED


def test_operation_idempotency_blocks_same_key_different_payload():
    store = OperationIdempotencyStore()
    payload = {"customer_id": "cust-123", "amount_usd": 500}
    key = deterministic_operation_key(
        tenant_id="tenant-acme",
        operation="account_credit",
        resource_id="cust-123",
        payload=payload,
        approval_id="apr-123",
    )
    _, first = store.begin_or_get(tenant_id="tenant-acme", idempotency_key=key, payload=payload)
    assert first is True
    _, second = store.begin_or_get(tenant_id="tenant-acme", idempotency_key=key, payload=payload)
    assert second is False

    try:
        store.begin_or_get(tenant_id="tenant-acme", idempotency_key=key, payload={"customer_id": "cust-123", "amount_usd": 5000})
    except RuntimeError as exc:
        assert "different payload" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("same idempotency key with different payload should fail")
