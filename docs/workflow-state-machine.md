# Workflow State Machine

Maci uses durable workflow state so a workflow can be reconstructed after timeout, crash, deploy interruption, or partial failure.

The Lambda runtime can be stateless.

The workflow state cannot be.

---

## Implemented module

```text
src/maci/recovery.py
```

Main types:

```text
WorkflowStateStore
WorkflowStateRecord
WorkflowStatus
ResumePolicy
RecoveryDecision
RecoveryOutcome
RecoveryDaemon
```

---

## Workflow states

The current state enum is:

```text
received
identity_bound
policy_checked
guardrail_passed
planning_started
customer_lookup_done
billing_check_done
ticket_created
waiting_for_approval
approved
credit_executed
final_response_sent
failed_safe
escalated_to_human
```

These states are intentionally explicit. After restart, the system should not ask the LLM where the workflow was. It should load the durable workflow state.

---

## State categories

### Safe auto-resume states

```text
received
identity_bound
policy_checked
guardrail_passed
planning_started
```

These states are early enough that automatic resume can be requested.

### Idempotent resume states

```text
customer_lookup_done
billing_check_done
ticket_created
```

These states are near or after business operations. Resume requires idempotency protection.

### Human-review states

```text
waiting_for_approval
approved
```

These states are approval-adjacent. The recovery daemon should not execute high-risk business actions directly from these states. It should escalate to human review or route through the normal approval/tool path.

### Terminal states

```text
credit_executed
final_response_sent
failed_safe
escalated_to_human
```

Terminal states are not recovered automatically.

---

## Resume policies

```text
auto_resume
idempotent_resume
human_review_required
do_not_resume
```

### auto_resume

Used when the workflow is in a safe early state and no business write has occurred.

### idempotent_resume

Used when the workflow is in a state where retry may touch an external operation. The workflow must have an idempotency key.

### human_review_required

Used when state is high-risk, approval-adjacent, ambiguous, or cannot be safely resumed automatically.

### do_not_resume

Used for terminal or explicitly unsafe states.

---

## Durable recovery fields

`WorkflowStateRecord` contains recovery coordination fields:

```text
recovery_partition
recovery_due_at_epoch
recovery_owner
recovery_lease_until
recovery_attempts
last_recovery_at
```

These make scheduled recovery safe across overlapping Lambda invocations.

---

## Lease model

The recovery daemon uses a conditional lease.

A daemon may process a workflow only if:

```text
recovery_owner is empty
or recovery_lease_until has expired
```

After claim:

```text
recovery_owner = <daemon invocation id>
recovery_lease_until = now + lease_seconds
recovery_attempts += 1
```

If another daemon invocation already owns the lease, the workflow is skipped with `lease_busy`.

---

## Retry and backoff

Recovery is bounded.

The daemon uses:

```text
RECOVERY_BACKOFF_SECONDS
RECOVERY_MAX_BACKOFF_SECONDS
RECOVERY_MAX_ATTEMPTS
```

When max attempts are exceeded, the workflow is escalated to human review instead of retrying forever.

---

## Recovery decision examples

### Crash before model planning

```text
state = policy_checked
policy = auto_resume
action = resume_requested
```

### Crash after ticket creation

```text
state = ticket_created
policy = idempotent_resume
action = idempotent_resume_requested
```

The resume path must not create a duplicate ticket.

### Crash around account credit approval

```text
state = waiting_for_approval
policy = human_review_required
action = escalated_to_human
```

The daemon must not apply account credit directly.

### Final response already sent

```text
state = final_response_sent
policy = do_not_resume
action = skipped
```

---

## Idempotency requirement

Write-adjacent workflow states must have an idempotency key before idempotent resume can be requested.

Examples:

```text
ticket_creation idempotency key:
tenant_id + conversation_id + customer_id + issue_type

account_credit idempotency key:
tenant_id + approval_id + payload_hash
```

If idempotent resume is needed but no idempotency key exists, the daemon escalates to human review.

---

## What the daemon does not do

The daemon does not directly execute high-risk business actions.

It does not directly:

- apply account credit;
- issue refunds;
- change permissions;
- delete data;
- bypass approval;
- override policy.

It reconstructs state, classifies the resume path, audits the decision, and routes the workflow toward safe resume or human review.
