# Recovery Daemon Operating Model

The recovery daemon is the scheduled reconciliation component for stale or interrupted workflows.

It exists because production agent workflows can fail halfway through:

- Lambda timeout;
- Bedrock timeout or throttling;
- deployment interruption;
- Step Functions retry boundary;
- DynamoDB conditional write conflict;
- external backend timeout;
- approval flow interruption;
- process/container restart.

The daemon makes the runtime stateless while keeping workflow recovery deterministic.

---

## Implemented module

```text
src/maci/recovery.py
```

Entrypoint:

```text
maci.recovery.lambda_handler
```

Deployment resources:

```text
EventBridge scheduled rule
RecoveryDaemonFunction Lambda
Workflow state DynamoDB table
recovery_due_index GSI
```

---

## Industry pattern used

The daemon follows a standard reconciliation-worker pattern:

```text
1. Persist workflow state.
2. Index records due for recovery.
3. Claim a record with a conditional lease.
4. Classify resume policy.
5. Use bounded retry/backoff.
6. Require idempotency for write-adjacent resume.
7. Escalate ambiguous/high-risk states to human review.
8. Emit audit and operational status.
```

---

## Why a daemon instead of just retries?

Retries handle immediate transient failure.

A recovery daemon handles workflows that were left incomplete after the original execution context disappeared.

Examples:

```text
The Lambda timed out after creating a ticket.
A deploy interrupted the request after approval was created.
Bedrock throttling happened after billing_check.
A Step Functions execution stopped before final response.
```

Without durable recovery, the system may:

- forget that a ticket was already created;
- duplicate a write action;
- lose a pending approval;
- incorrectly claim that an action completed;
- force a user to restart from scratch;
- fail to audit the failure path.

---

## Recovery scan

The daemon scans records due for recovery.

In AWS mode, the intended access pattern uses the DynamoDB GSI:

```text
recovery_due_index
  partition key: recovery_partition
  sort key: recovery_due_at_epoch
```

Typical due record:

```text
recovery_partition = active
recovery_due_at_epoch <= now
```

This avoids scanning the full workflow table during normal operation.

---

## Lease and fencing

A scheduled Lambda can overlap with another scheduled Lambda.

The daemon therefore uses conditional lease acquisition.

A worker can claim a workflow only if:

```text
no owner exists
or lease expired
```

On claim:

```text
recovery_owner = current daemon invocation
recovery_lease_until = now + RECOVERY_LEASE_SECONDS
recovery_attempts += 1
last_recovery_at = now
```

This prevents two daemon invocations from processing the same workflow at the same time.

---

## Resume classification

The daemon classifies the workflow using the durable status.

| Workflow state | Resume policy | Reason |
|---|---|---|
| `received` | `auto_resume` | No business operation has happened yet |
| `policy_checked` | `auto_resume` | Safe early state |
| `customer_lookup_done` | `idempotent_resume` | Read result exists; resume must avoid duplication |
| `billing_check_done` | `idempotent_resume` | Business context exists; resume with idempotency |
| `ticket_created` | `idempotent_resume` | Write may already exist; no duplicate ticket |
| `waiting_for_approval` | `human_review_required` | High-risk boundary |
| `approved` | `human_review_required` | Approval-adjacent ambiguity |
| `credit_executed` | `do_not_resume` | Terminal business action |
| `final_response_sent` | `do_not_resume` | Terminal user response |
| `failed_safe` | `do_not_resume` | Already stopped safely |
| `escalated_to_human` | `do_not_resume` | Already escalated |

---

## Actions emitted by the daemon

```text
resume_requested
idempotent_resume_requested
escalated_to_human
skipped
lease_busy
max_attempts_exceeded
```

These are recovery decisions, not direct high-risk business executions.

---

## Backoff and maximum attempts

The daemon uses bounded retry and backoff.

Environment variables:

```text
RECOVERY_STALE_SECONDS
RECOVERY_LEASE_SECONDS
RECOVERY_BACKOFF_SECONDS
RECOVERY_MAX_BACKOFF_SECONDS
RECOVERY_MAX_ATTEMPTS
RECOVERY_MAX_ITEMS
RECOVERY_TENANT_IDS
```

If attempts exceed the maximum, the workflow is escalated to human review.

---

## Conversation status update

When a recovery decision is made, the daemon can append a non-user-visible system status message to the conversation transcript.

Example:

```json
{
  "recovery_action": "escalated_to_human",
  "workflow_id": "wf-123",
  "resume_policy": "human_review_required",
  "reason": "approval-adjacent state requires human review",
  "next_recovery_at": null
}
```

This helps operators reconstruct the workflow without exposing internal recovery details as a normal assistant response.

---

## Audit behavior

Every recovery decision should emit an audit event.

Example event type:

```text
recovery_action
```

The audit event should include:

```text
tenant_id
conversation_id
workflow_id
status
resume_policy
action
reason
recovery_owner
recovery_attempts
next_recovery_at
```

---

## Fail-closed behavior

The recovery daemon must not directly execute high-risk business operations.

If state is ambiguous around:

- account credit;
- refund;
- billing adjustment;
- permission escalation;
- data deletion;

then the daemon should escalate to human review or route through the normal policy/approval/tool path.

---

## Operational expectations

Operators should monitor:

```text
number of processed recovery records
number of lease_busy outcomes
number of escalations
number of max-attempt failures
age of oldest active workflow
recovery Lambda errors
DynamoDB conditional write failures
```

A high number of recoveries may indicate upstream instability.

A high number of escalations may indicate unsafe or ambiguous state modeling.

---

## Current limitations

The v0.1.6 daemon provides the foundation:

- due record scan;
- conditional lease;
- resume classification;
- retry/backoff;
- human escalation;
- audit/status emission.

Production systems still need to wire the resume action into the selected orchestrator:

- Step Functions resume/re-drive;
- queue-based task dispatch;
- manual review UI;
- runbook-based operator workflow;
- backend reconciliation for external systems.
