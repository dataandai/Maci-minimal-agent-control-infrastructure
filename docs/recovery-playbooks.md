# Recovery Playbooks

This document describes specific recovery scenarios and expected operator behavior.

---

## Playbook 1: Lambda timeout before tool execution

State example:

```text
status = planning_started
```

Expected daemon classification:

```text
resume_policy = auto_resume
action = resume_requested
```

Operator action:

```text
monitor retry
check repeated failures
escalate if max attempts exceeded
```

---

## Playbook 2: Crash after customer lookup

State example:

```text
status = customer_lookup_done
```

Expected daemon classification:

```text
resume_policy = idempotent_resume
action = idempotent_resume_requested
```

Reason:

```text
The workflow has already used a business resource result. Resume must avoid duplicating downstream writes.
```

---

## Playbook 3: Crash after ticket creation

State example:

```text
status = ticket_created
idempotency_key = ticket:<tenant>:<conversation>:<customer>:billing_dispute
```

Expected daemon classification:

```text
resume_policy = idempotent_resume
action = idempotent_resume_requested
```

Required checks:

```text
idempotency record exists
ticket ID exists in metadata/tool result/external backend
no duplicate ticket created on retry
```

If idempotency key is missing:

```text
escalate_to_human
```

---

## Playbook 4: Account credit waiting for approval

State example:

```text
status = waiting_for_approval
approval_id = appr-999
```

Expected daemon classification:

```text
resume_policy = human_review_required
action = escalated_to_human
```

Reason:

```text
Approval-adjacent state is high-risk. The daemon must not execute account_credit directly.
```

Operator checks:

```text
approval record
conversation transcript
audit trail
billing backend state
payload hash
```

---

## Playbook 5: Approval approved but execution unknown

State example:

```text
status = approved
approval_id = appr-999
```

Expected daemon classification:

```text
resume_policy = human_review_required
action = escalated_to_human
```

Operator action:

```text
check idempotency record
check billing backend for credit_id
check audit event account_credit_executed
if uncertain, do not blindly retry
route through approved normal tool path or manual review
```

---

## Playbook 6: Max recovery attempts exceeded

State example:

```text
recovery_attempts > RECOVERY_MAX_ATTEMPTS
```

Expected daemon classification:

```text
action = max_attempts_exceeded
workflow status = escalated_to_human
```

Operator action:

```text
inspect last_error
inspect trace/audit/conversation
fix underlying cause
manually decide resume/fail/close
```

---

## Playbook 7: Lease busy

State example:

```text
recovery_owner = another-worker
recovery_lease_until > now
```

Expected daemon classification:

```text
action = lease_busy
```

Operator action:

```text
usually none
if stuck, wait for lease expiry
if repeated, check daemon overlap and Lambda duration
```

---

## Playbook 8: Recovery daemon misbehaves

Immediate action:

```text
pause EventBridge recovery rule
enable relevant kill switch if needed
preserve logs/audit
review recent recovery outcomes
```

Then check:

```text
workflow state table
lease fields
backoff fields
recent code deploy
IAM permissions
DynamoDB conditional write errors
```

---

## Manual recovery safety rule

For high-risk business actions:

```text
no approval, no execution
payload mismatch, no execution
unknown external write state, no blind retry
missing idempotency key, human review
```
