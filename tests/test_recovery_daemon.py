from datetime import datetime, timedelta, timezone

from maci.conversation import ConversationMessageType, ConversationStore
from maci.recovery import RecoveryAction, RecoveryDaemon, ResumePolicy, WorkflowStateStore, WorkflowStatus
from maci.schemas import TenantContext


def _ctx(request_id: str = "wf-1") -> TenantContext:
    return TenantContext(tenant_id="tenant-acme", user_id="u-1", request_id=request_id, agent_id="agent-acme-support")


def _make_due(store: WorkflowStateStore, *, request_id: str, status: WorkflowStatus, conversation_id: str, **kwargs):
    ctx = _ctx(request_id)
    record = store.transition(ctx, conversation_id=conversation_id, status=status, **kwargs)
    due = record.model_copy(update={"recovery_due_at_epoch": int((datetime.now(timezone.utc) - timedelta(seconds=1)).timestamp())})
    store.put(due)
    return due


def test_recovery_daemon_claims_stale_workflow_with_lease_and_backoff():
    store = WorkflowStateStore(recovery_grace_seconds=0)
    conv_store = ConversationStore()
    ctx = _ctx("wf-auto")
    conv_store.start_or_resume(ctx, conversation_id="conv-auto")
    _make_due(store, request_id="wf-auto", status=WorkflowStatus.PLANNING_STARTED, conversation_id="conv-auto")

    daemon = RecoveryDaemon(workflow_store=store, conversation_store=conv_store, owner_id="daemon-a", backoff_seconds=60)
    outcomes = daemon.run_due(limit=10)

    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.action == RecoveryAction.RESUME_REQUESTED
    assert outcome.resume_policy == ResumePolicy.AUTO_RESUME

    record = store.get("tenant-acme", "wf-auto")
    assert record.recovery_owner is None
    assert record.recovery_attempts == 1
    assert record.recovery_due_at_epoch > int(datetime.now(timezone.utc).timestamp())
    assert record.metadata["recovery_action"] == RecoveryAction.RESUME_REQUESTED.value

    messages = conv_store.list_messages("tenant-acme", "conv-auto")
    assert messages[-1].message_type == ConversationMessageType.SYSTEM_STATUS
    assert messages[-1].visible_to_user is False


def test_recovery_daemon_does_not_double_claim_active_lease():
    store = WorkflowStateStore(recovery_grace_seconds=0)
    due = _make_due(store, request_id="wf-lease", status=WorkflowStatus.PLANNING_STARTED, conversation_id="conv-lease")
    claimed = store.try_claim(due, owner_id="daemon-a", lease_seconds=120)
    assert claimed is not None

    daemon_b = RecoveryDaemon(workflow_store=store, owner_id="daemon-b")
    outcomes = daemon_b.run_due(limit=10)
    assert outcomes == ()


def test_recovery_daemon_requires_idempotency_key_for_write_resume():
    store = WorkflowStateStore(recovery_grace_seconds=0)
    _make_due(store, request_id="wf-ticket", status=WorkflowStatus.TICKET_CREATED, conversation_id="conv-ticket")

    outcomes = RecoveryDaemon(workflow_store=store, owner_id="daemon-a").run_due(limit=10)

    assert outcomes[0].action == RecoveryAction.ESCALATED_TO_HUMAN
    assert outcomes[0].resume_policy == ResumePolicy.IDEMPOTENT_RESUME
    assert store.get("tenant-acme", "wf-ticket").status == WorkflowStatus.ESCALATED_TO_HUMAN


def test_recovery_daemon_allows_idempotent_resume_when_key_exists():
    store = WorkflowStateStore(recovery_grace_seconds=0)
    _make_due(
        store,
        request_id="wf-ticket",
        status=WorkflowStatus.TICKET_CREATED,
        conversation_id="conv-ticket",
        idempotency_key="ticket-key-123",
    )

    outcomes = RecoveryDaemon(workflow_store=store, owner_id="daemon-a").run_due(limit=10)

    assert outcomes[0].action == RecoveryAction.IDEMPOTENT_RESUME_REQUESTED
    assert store.get("tenant-acme", "wf-ticket").metadata["recovery_resume_policy"] == ResumePolicy.IDEMPOTENT_RESUME.value


def test_recovery_daemon_escalates_approval_adjacent_state():
    store = WorkflowStateStore(recovery_grace_seconds=0)
    _make_due(
        store,
        request_id="wf-approval",
        status=WorkflowStatus.WAITING_FOR_APPROVAL,
        conversation_id="conv-approval",
        approval_id="apr-123",
    )

    outcomes = RecoveryDaemon(workflow_store=store, owner_id="daemon-a").run_due(limit=10)

    assert outcomes[0].action == RecoveryAction.ESCALATED_TO_HUMAN
    assert outcomes[0].resume_policy == ResumePolicy.HUMAN_REVIEW_REQUIRED
    assert store.get("tenant-acme", "wf-approval").status == WorkflowStatus.ESCALATED_TO_HUMAN


def test_recovery_daemon_escalates_after_bounded_retries():
    store = WorkflowStateStore(recovery_grace_seconds=0)
    record = _make_due(store, request_id="wf-retry", status=WorkflowStatus.PLANNING_STARTED, conversation_id="conv-retry")
    store.put(record.model_copy(update={"recovery_attempts": 3}))

    outcomes = RecoveryDaemon(workflow_store=store, owner_id="daemon-a", max_attempts=3).run_due(limit=10)

    assert outcomes[0].action == RecoveryAction.MAX_ATTEMPTS_EXCEEDED
    assert store.get("tenant-acme", "wf-retry").status == WorkflowStatus.ESCALATED_TO_HUMAN
