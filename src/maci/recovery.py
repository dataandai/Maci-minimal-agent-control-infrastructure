from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Iterable
from uuid import uuid4

from pydantic import Field

from .schemas import StrictModel, TenantContext

logger = logging.getLogger("maci.recovery")


class WorkflowStatus(str, Enum):
    RECEIVED = "received"
    IDENTITY_BOUND = "identity_bound"
    POLICY_CHECKED = "policy_checked"
    GUARDRAIL_PASSED = "guardrail_passed"
    PLANNING_STARTED = "planning_started"
    CUSTOMER_LOOKUP_DONE = "customer_lookup_done"
    BILLING_CHECK_DONE = "billing_check_done"
    TICKET_CREATED = "ticket_created"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    APPROVED = "approved"
    CREDIT_EXECUTED = "credit_executed"
    FINAL_RESPONSE_SENT = "final_response_sent"
    FAILED_SAFE = "failed_safe"
    ESCALATED_TO_HUMAN = "escalated_to_human"


class ResumePolicy(str, Enum):
    AUTO_RESUME = "auto_resume"
    IDEMPOTENT_RESUME = "idempotent_resume"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    DO_NOT_RESUME = "do_not_resume"


class RecoveryAction(str, Enum):
    RESUME_REQUESTED = "resume_requested"
    IDEMPOTENT_RESUME_REQUESTED = "idempotent_resume_requested"
    ESCALATED_TO_HUMAN = "escalated_to_human"
    SKIPPED = "skipped"
    LEASE_BUSY = "lease_busy"
    MAX_ATTEMPTS_EXCEEDED = "max_attempts_exceeded"


class WorkflowStateRecord(StrictModel):
    tenant_id: str
    conversation_id: str
    request_id: str
    workflow_id: str
    status: WorkflowStatus
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pending_action: str | None = None
    approval_id: str | None = None
    idempotency_key: str | None = None
    last_error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Recovery daemon fields.
    # These are the durable coordination fields that make the Lambda runtime
    # stateless while keeping recovery decisions stable across restarts.
    recovery_partition: str = "active"
    recovery_due_at_epoch: int = 0
    recovery_owner: str | None = None
    recovery_lease_until: datetime | None = None
    recovery_attempts: int = 0
    last_recovery_at: datetime | None = None


class RecoveryDecision(StrictModel):
    tenant_id: str
    conversation_id: str
    workflow_id: str
    status: WorkflowStatus
    resume_policy: ResumePolicy
    reason: str


class RecoveryOutcome(StrictModel):
    tenant_id: str
    conversation_id: str
    workflow_id: str
    status: WorkflowStatus
    resume_policy: ResumePolicy
    action: RecoveryAction
    reason: str
    recovery_owner: str
    recovery_attempts: int
    next_recovery_at: datetime | None = None


_SAFE_AUTO_STATES = {
    WorkflowStatus.RECEIVED,
    WorkflowStatus.IDENTITY_BOUND,
    WorkflowStatus.POLICY_CHECKED,
    WorkflowStatus.GUARDRAIL_PASSED,
    WorkflowStatus.PLANNING_STARTED,
}

_IDEMPOTENT_STATES = {
    WorkflowStatus.CUSTOMER_LOOKUP_DONE,
    WorkflowStatus.BILLING_CHECK_DONE,
    WorkflowStatus.TICKET_CREATED,
}

_HUMAN_REVIEW_STATES = {
    WorkflowStatus.WAITING_FOR_APPROVAL,
    WorkflowStatus.APPROVED,
}

_TERMINAL_STATES = {
    WorkflowStatus.CREDIT_EXECUTED,
    WorkflowStatus.FINAL_RESPONSE_SENT,
    WorkflowStatus.FAILED_SAFE,
    WorkflowStatus.ESCALATED_TO_HUMAN,
}

_ACTIVE_PARTITION = "active"
_TERMINAL_PARTITION = "terminal"


def _recovery_shard_count() -> int:
    try:
        return max(1, int(os.getenv("RECOVERY_ACTIVE_SHARDS", "8")))
    except ValueError:
        return 8


def _active_partition_for(workflow_id: str) -> str:
    """Spread active workflows across N GSI partitions to avoid a hot partition.

    A single constant partition key value ("active") funnels every active
    workflow onto one physical GSI partition, which throttles at scale. Hashing
    the workflow id into a bounded set of shard keys keeps scans cheap while
    distributing write/read load.
    """

    shards = _recovery_shard_count()
    if shards <= 1:
        return _ACTIVE_PARTITION
    import hashlib

    bucket = int(hashlib.sha256(workflow_id.encode("utf-8")).hexdigest(), 16) % shards
    return f"{_ACTIVE_PARTITION}#{bucket}"


def _active_partitions() -> tuple[str, ...]:
    shards = _recovery_shard_count()
    if shards <= 1:
        return (_ACTIVE_PARTITION,)
    # Include the bare "active" value so records written before sharding was
    # enabled are still discovered by the recovery daemon.
    return (_ACTIVE_PARTITION, *(f"{_ACTIVE_PARTITION}#{i}" for i in range(shards)))


def _is_active_partition(partition: str) -> bool:
    return partition == _ACTIVE_PARTITION or partition.startswith(f"{_ACTIVE_PARTITION}#")


@dataclass
class WorkflowStateStore:
    """Persistent workflow state store for restart/recovery decisions.

    Lambda runtime can be stateless, but workflow state must not be. This store
    keeps durable status records and a lease/fencing model so a scheduled
    recovery daemon can safely reconcile stale workflows after crash, timeout,
    partial deploy, or Step Functions retry.

    Industry pattern used here:
    - durable workflow state in DynamoDB;
    - a global recovery-due index for scheduled scans;
    - conditional lease acquisition with expiry;
    - bounded retry attempts with backoff;
    - idempotent-write and human-review boundaries;
    - fail-closed escalation when state is ambiguous.
    """

    table_name: str | None = None
    table: object | None = None
    memory: dict[tuple[str, str], WorkflowStateRecord] = field(default_factory=dict)
    recovery_grace_seconds: int = field(default_factory=lambda: int(os.getenv("RECOVERY_STALE_SECONDS", "300")))

    def __post_init__(self) -> None:
        self.table_name = self.table_name or os.getenv("WORKFLOW_STATE_TABLE_NAME")
        if self.table_name and self.table is None:
            from ._aws import dynamodb_table

            self.table = dynamodb_table(self.table_name)

    def transition(
        self,
        tenant_context: TenantContext,
        *,
        conversation_id: str,
        status: WorkflowStatus,
        workflow_id: str | None = None,
        pending_action: str | None = None,
        approval_id: str | None = None,
        idempotency_key: str | None = None,
        last_error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WorkflowStateRecord:
        workflow_id = workflow_id or tenant_context.request_id
        existing = self.get(tenant_context.tenant_id, workflow_id)
        now = datetime.now(timezone.utc)
        terminal = status in _TERMINAL_STATES
        record = WorkflowStateRecord(
            tenant_id=tenant_context.tenant_id,
            conversation_id=conversation_id,
            request_id=tenant_context.request_id,
            workflow_id=workflow_id,
            status=status,
            created_at=existing.created_at if existing else now,
            updated_at=now,
            pending_action=pending_action if pending_action is not None else (existing.pending_action if existing else None),
            approval_id=approval_id if approval_id is not None else (existing.approval_id if existing else None),
            idempotency_key=idempotency_key if idempotency_key is not None else (existing.idempotency_key if existing else None),
            last_error=last_error,
            metadata={**(existing.metadata if existing else {}), **(metadata or {})},
            recovery_partition=_TERMINAL_PARTITION if terminal else _active_partition_for(workflow_id),
            recovery_due_at_epoch=0 if terminal else int((now + timedelta(seconds=self.recovery_grace_seconds)).timestamp()),
            recovery_owner=None,
            recovery_lease_until=None,
            recovery_attempts=existing.recovery_attempts if existing else 0,
            last_recovery_at=existing.last_recovery_at if existing else None,
        )
        self.put(record)
        return record

    def put(self, record: WorkflowStateRecord) -> None:
        if self.table is not None:
            self.table.put_item(Item=_to_dynamodb_item(record.model_dump(mode="json")))  # type: ignore[attr-defined]
            return
        self.memory[(record.tenant_id, record.workflow_id)] = record

    def get(self, tenant_id: str, workflow_id: str) -> WorkflowStateRecord | None:
        if self.table is not None:
            item = self.table.get_item(Key={"tenant_id": tenant_id, "workflow_id": workflow_id}).get("Item")  # type: ignore[attr-defined]
            return WorkflowStateRecord.model_validate(_from_dynamodb_item(item)) if item else None
        return self.memory.get((tenant_id, workflow_id))

    def list_incomplete(self, tenant_id: str) -> tuple[WorkflowStateRecord, ...]:
        if self.table is not None:
            response = self.table.query(  # type: ignore[attr-defined]
                KeyConditionExpression="tenant_id = :tenant",
                ExpressionAttributeValues={":tenant": tenant_id},
            )
            records = [WorkflowStateRecord.model_validate(_from_dynamodb_item(item)) for item in response.get("Items", [])]
        else:
            records = [record for (record_tenant, _), record in self.memory.items() if record_tenant == tenant_id]
        return tuple(record for record in records if record.status not in _TERMINAL_STATES)

    def list_due_records(self, *, now: datetime | None = None, limit: int = 25, tenant_ids: Iterable[str] | None = None) -> tuple[WorkflowStateRecord, ...]:
        """Return stale recoverable records.

        DynamoDB deployments should use the `recovery_due_index` GSI. The code
        falls back to a bounded scan if the index is absent during early lab
        deployments. Local mode uses the in-memory store.
        """

        now = now or datetime.now(timezone.utc)
        due_epoch = int(now.timestamp())
        tenant_set = set(tenant_ids or [])

        if self.table is not None:
            items: list[Any] = []
            for partition in _active_partitions():
                try:
                    from boto3.dynamodb.conditions import Key  # type: ignore

                    response = self.table.query(  # type: ignore[attr-defined]
                        IndexName="recovery_due_index",
                        KeyConditionExpression=Key("recovery_partition").eq(partition) & Key("recovery_due_at_epoch").lte(due_epoch),
                        Limit=limit,
                    )
                    items.extend(response.get("Items", []))
                except Exception:
                    response = self.table.scan(  # type: ignore[attr-defined]
                        FilterExpression="recovery_partition = :active AND recovery_due_at_epoch <= :due",
                        ExpressionAttributeValues={":active": partition, ":due": due_epoch},
                        Limit=limit,
                    )
                    items.extend(response.get("Items", []))
            records = [WorkflowStateRecord.model_validate(_from_dynamodb_item(item)) for item in items]
        else:
            records = list(self.memory.values())

        due_records = [
            record
            for record in records
            if record.status not in _TERMINAL_STATES
            and _is_active_partition(record.recovery_partition)
            and record.recovery_due_at_epoch <= due_epoch
            and (not tenant_set or record.tenant_id in tenant_set)
            and _lease_expired(record, now)
        ]
        return tuple(sorted(due_records, key=lambda record: (record.recovery_due_at_epoch, record.updated_at))[:limit])

    def try_claim(self, record: WorkflowStateRecord, *, owner_id: str, lease_seconds: int, now: datetime | None = None) -> WorkflowStateRecord | None:
        now = now or datetime.now(timezone.utc)
        lease_until = now + timedelta(seconds=lease_seconds)

        if self.table is not None:
            try:
                response = self.table.update_item(  # type: ignore[attr-defined]
                    Key={"tenant_id": record.tenant_id, "workflow_id": record.workflow_id},
                    UpdateExpression="SET recovery_owner = :owner, recovery_lease_until = :lease, "
                    "recovery_attempts = if_not_exists(recovery_attempts, :zero) + :one, last_recovery_at = :now_iso",
                    ConditionExpression="recovery_partition = :active AND #status = :status AND "
                    "(attribute_not_exists(recovery_lease_until) OR recovery_lease_until < :now_iso)",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":owner": owner_id,
                        ":lease": lease_until.isoformat(),
                        ":zero": 0,
                        ":one": 1,
                        ":now_iso": now.isoformat(),
                        ":active": record.recovery_partition,
                        ":status": record.status.value,
                    },
                    ReturnValues="ALL_NEW",
                )
                return WorkflowStateRecord.model_validate(_from_dynamodb_item(response["Attributes"]))
            except Exception as exc:
                # Usually a benign lease conflict (another worker holds it); a
                # persistent DynamoDB error here would otherwise be invisible.
                logger.debug("recovery lease not acquired for %s/%s: %s", record.tenant_id, record.workflow_id, exc)
                return None

        current = self.memory.get((record.tenant_id, record.workflow_id))
        if current is None or current.status != record.status or not _is_active_partition(current.recovery_partition) or not _lease_expired(current, now):
            return None
        claimed = current.model_copy(
            update={
                "recovery_owner": owner_id,
                "recovery_lease_until": lease_until,
                "recovery_attempts": current.recovery_attempts + 1,
                "last_recovery_at": now,
            }
        )
        self.memory[(claimed.tenant_id, claimed.workflow_id)] = claimed
        return claimed

    def release_for_retry(self, record: WorkflowStateRecord, *, next_recovery_at: datetime, metadata: dict[str, Any] | None = None) -> WorkflowStateRecord:
        updated = record.model_copy(
            update={
                "recovery_owner": None,
                "recovery_lease_until": None,
                "recovery_due_at_epoch": int(next_recovery_at.timestamp()),
                "updated_at": datetime.now(timezone.utc),
                "metadata": {**record.metadata, **(metadata or {})},
            }
        )
        self.put(updated)
        return updated

    def mark_escalated(self, record: WorkflowStateRecord, *, reason: str, metadata: dict[str, Any] | None = None) -> WorkflowStateRecord:
        now = datetime.now(timezone.utc)
        updated = record.model_copy(
            update={
                "status": WorkflowStatus.ESCALATED_TO_HUMAN,
                "last_error": reason,
                "updated_at": now,
                "recovery_partition": "terminal",
                "recovery_due_at_epoch": 0,
                "recovery_owner": None,
                "recovery_lease_until": None,
                "metadata": {**record.metadata, **(metadata or {})},
            }
        )
        self.put(updated)
        return updated

    def recovery_decision(self, record: WorkflowStateRecord) -> RecoveryDecision:
        if record.status in _SAFE_AUTO_STATES:
            policy = ResumePolicy.AUTO_RESUME
            reason = "read-only/planning state can be retried safely"
        elif record.status in _IDEMPOTENT_STATES:
            policy = ResumePolicy.IDEMPOTENT_RESUME
            reason = "state may include external writes; resume only through idempotency key checks"
        elif record.status in _HUMAN_REVIEW_STATES:
            policy = ResumePolicy.HUMAN_REVIEW_REQUIRED
            reason = "high-risk or approval-adjacent state must be reconciled by a human or exact approval/payload check"
        else:
            policy = ResumePolicy.DO_NOT_RESUME
            reason = "terminal or unsafe state must not be replayed automatically"
        return RecoveryDecision(
            tenant_id=record.tenant_id,
            conversation_id=record.conversation_id,
            workflow_id=record.workflow_id,
            status=record.status,
            resume_policy=policy,
            reason=reason,
        )


@dataclass
class RecoveryScanner:
    """Classify incomplete workflow records without mutating them."""

    store: WorkflowStateStore

    def scan_tenant(self, tenant_id: str) -> tuple[RecoveryDecision, ...]:
        return tuple(self.store.recovery_decision(record) for record in self.store.list_incomplete(tenant_id))


@dataclass
class RecoveryDaemon:
    """Scheduled recovery reconciler with lease-based coordination.

    The daemon is intentionally conservative: it never replays high-risk
    business actions itself. It claims stale workflows, decides whether the next
    step is auto-resumable, idempotent-resumable, or human-review-only, records
    that decision, and lets the normal workflow/tool path perform any actual
    execution under the same policy/idempotency controls as live traffic.
    """

    workflow_store: WorkflowStateStore = field(default_factory=WorkflowStateStore)
    conversation_store: object | None = None
    audit_logger: object | None = None
    owner_id: str = field(default_factory=lambda: f"recovery-{uuid4().hex[:12]}")
    lease_seconds: int = field(default_factory=lambda: int(os.getenv("RECOVERY_LEASE_SECONDS", "120")))
    max_attempts: int = field(default_factory=lambda: int(os.getenv("RECOVERY_MAX_ATTEMPTS", "3")))
    backoff_seconds: int = field(default_factory=lambda: int(os.getenv("RECOVERY_BACKOFF_SECONDS", "60")))
    max_backoff_seconds: int = field(default_factory=lambda: int(os.getenv("RECOVERY_MAX_BACKOFF_SECONDS", "3600")))
    now_fn: Callable[[], datetime] = field(default_factory=lambda: lambda: datetime.now(timezone.utc))

    def run_due(self, *, tenant_ids: Iterable[str] | None = None, limit: int = 25) -> tuple[RecoveryOutcome, ...]:
        now = self.now_fn()
        outcomes: list[RecoveryOutcome] = []
        for due in self.workflow_store.list_due_records(now=now, limit=limit, tenant_ids=tenant_ids):
            claimed = self.workflow_store.try_claim(due, owner_id=self.owner_id, lease_seconds=self.lease_seconds, now=now)
            if claimed is None:
                outcomes.append(
                    RecoveryOutcome(
                        tenant_id=due.tenant_id,
                        conversation_id=due.conversation_id,
                        workflow_id=due.workflow_id,
                        status=due.status,
                        resume_policy=self.workflow_store.recovery_decision(due).resume_policy,
                        action=RecoveryAction.LEASE_BUSY,
                        reason="another recovery worker owns a non-expired lease",
                        recovery_owner=self.owner_id,
                        recovery_attempts=due.recovery_attempts,
                    )
                )
                continue
            outcomes.append(self._process_claimed(claimed, now=now))
        return tuple(outcomes)

    def _process_claimed(self, record: WorkflowStateRecord, *, now: datetime) -> RecoveryOutcome:
        decision = self.workflow_store.recovery_decision(record)

        if record.recovery_attempts > self.max_attempts:
            reason = f"maximum recovery attempts exceeded ({record.recovery_attempts}>{self.max_attempts})"
            self.workflow_store.mark_escalated(record, reason=reason, metadata={"recovery_action": RecoveryAction.MAX_ATTEMPTS_EXCEEDED.value})
            outcome = self._outcome(record, decision, RecoveryAction.MAX_ATTEMPTS_EXCEEDED, reason)
            self._append_recovery_status(outcome)
            self._emit_audit(outcome)
            return outcome

        if decision.resume_policy == ResumePolicy.HUMAN_REVIEW_REQUIRED:
            self.workflow_store.mark_escalated(record, reason=decision.reason, metadata={"recovery_action": RecoveryAction.ESCALATED_TO_HUMAN.value})
            outcome = self._outcome(record, decision, RecoveryAction.ESCALATED_TO_HUMAN, decision.reason)
            self._append_recovery_status(outcome)
            self._emit_audit(outcome)
            return outcome

        if decision.resume_policy == ResumePolicy.IDEMPOTENT_RESUME and not record.idempotency_key:
            reason = "idempotent resume requested but workflow has no idempotency key"
            self.workflow_store.mark_escalated(record, reason=reason, metadata={"recovery_action": RecoveryAction.ESCALATED_TO_HUMAN.value})
            outcome = self._outcome(record, decision, RecoveryAction.ESCALATED_TO_HUMAN, reason)
            self._append_recovery_status(outcome)
            self._emit_audit(outcome)
            return outcome

        if decision.resume_policy == ResumePolicy.DO_NOT_RESUME:
            next_recovery_at = now + timedelta(seconds=self._backoff(record.recovery_attempts))
            self.workflow_store.release_for_retry(record, next_recovery_at=next_recovery_at, metadata={"recovery_action": RecoveryAction.SKIPPED.value})
            outcome = self._outcome(record, decision, RecoveryAction.SKIPPED, decision.reason, next_recovery_at=next_recovery_at)
            self._append_recovery_status(outcome)
            self._emit_audit(outcome)
            return outcome

        action = RecoveryAction.RESUME_REQUESTED if decision.resume_policy == ResumePolicy.AUTO_RESUME else RecoveryAction.IDEMPOTENT_RESUME_REQUESTED
        next_recovery_at = now + timedelta(seconds=self._backoff(record.recovery_attempts))
        self.workflow_store.release_for_retry(
            record,
            next_recovery_at=next_recovery_at,
            metadata={
                "recovery_action": action.value,
                "recovery_resume_policy": decision.resume_policy.value,
                "recovery_reason": decision.reason,
            },
        )
        outcome = self._outcome(record, decision, action, decision.reason, next_recovery_at=next_recovery_at)
        self._append_recovery_status(outcome)
        self._emit_audit(outcome)
        return outcome

    def _outcome(
        self,
        record: WorkflowStateRecord,
        decision: RecoveryDecision,
        action: RecoveryAction,
        reason: str,
        *,
        next_recovery_at: datetime | None = None,
    ) -> RecoveryOutcome:
        return RecoveryOutcome(
            tenant_id=record.tenant_id,
            conversation_id=record.conversation_id,
            workflow_id=record.workflow_id,
            status=record.status,
            resume_policy=decision.resume_policy,
            action=action,
            reason=reason,
            recovery_owner=self.owner_id,
            recovery_attempts=record.recovery_attempts,
            next_recovery_at=next_recovery_at,
        )

    def _backoff(self, attempts: int) -> int:
        return min(self.max_backoff_seconds, max(self.backoff_seconds, self.backoff_seconds * (2 ** max(0, attempts - 1))))

    def _append_recovery_status(self, outcome: RecoveryOutcome) -> None:
        if self.conversation_store is None:
            return
        try:
            ctx = TenantContext(
                tenant_id=outcome.tenant_id,
                user_id="maci-recovery-daemon",
                request_id=f"recovery-{outcome.workflow_id}",
                agent_id="maci-recovery-daemon",
                conversation_id=outcome.conversation_id,
            )
            self.conversation_store.append_system_status(  # type: ignore[attr-defined]
                ctx,
                outcome.conversation_id,
                {
                    "recovery_action": outcome.action.value,
                    "workflow_id": outcome.workflow_id,
                    "resume_policy": outcome.resume_policy.value,
                    "reason": outcome.reason,
                    "next_recovery_at": outcome.next_recovery_at.isoformat() if outcome.next_recovery_at else None,
                },
            )
        except Exception:
            # Recovery must not crash because transcript storage failed. The audit
            # path still records the decision when available.
            logger.exception("recovery transcript status write failed for workflow %s", outcome.workflow_id)
            return

    def _emit_audit(self, outcome: RecoveryOutcome) -> None:
        if self.audit_logger is None:
            return
        try:
            from .audit import AuditEvent, AuditEventType

            self.audit_logger.emit(  # type: ignore[attr-defined]
                AuditEvent(
                    request_id=f"recovery-{outcome.workflow_id}",
                    tenant_id=outcome.tenant_id,
                    event_type=AuditEventType.RECOVERY_ACTION,
                    message="recovery daemon reconciled stale workflow",
                    attributes=outcome.model_dump(mode="json"),
                )
            )
        except Exception:
            logger.exception("recovery audit emit failed for workflow %s", outcome.workflow_id)
            return


def lambda_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """EventBridge-compatible recovery daemon Lambda handler.

    Event examples:
    - {"max_items": 25}
    - {"tenant_id": "tenant-acme", "max_items": 10}
    - {"tenant_ids": ["tenant-acme", "tenant-contoso"]}
    """

    from .audit import AuditLogger
    from .conversation import ConversationStore

    tenant_ids = _tenant_ids_from_event(event)
    max_items = int(event.get("max_items") or os.getenv("RECOVERY_MAX_ITEMS") or "25")
    owner_id = getattr(context, "aws_request_id", None) or event.get("owner_id") or f"recovery-{uuid4().hex[:12]}"
    daemon = RecoveryDaemon(
        workflow_store=WorkflowStateStore(),
        conversation_store=ConversationStore(),
        audit_logger=AuditLogger(),
        owner_id=str(owner_id),
    )
    outcomes = daemon.run_due(tenant_ids=tenant_ids, limit=max_items)
    return {
        "ok": True,
        "recovery_owner": daemon.owner_id,
        "processed": len(outcomes),
        "outcomes": [outcome.model_dump(mode="json") for outcome in outcomes],
    }


def _tenant_ids_from_event(event: dict[str, Any]) -> tuple[str, ...] | None:
    if event.get("tenant_id"):
        return (str(event["tenant_id"]),)
    if event.get("tenant_ids"):
        return tuple(str(value) for value in event["tenant_ids"])
    env_value = os.getenv("RECOVERY_TENANT_IDS", "").strip()
    if env_value:
        return tuple(part.strip() for part in env_value.split(",") if part.strip())
    return None


def _lease_expired(record: WorkflowStateRecord, now: datetime) -> bool:
    return record.recovery_lease_until is None or record.recovery_lease_until <= now


def _to_dynamodb_item(value: Any) -> Any:
    from decimal import Decimal

    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _to_dynamodb_item(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_to_dynamodb_item(v) for v in value]
    return value


def _from_dynamodb_item(value: Any) -> Any:
    from decimal import Decimal

    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    if isinstance(value, dict):
        return {k: _from_dynamodb_item(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_from_dynamodb_item(v) for v in value]
    return value
