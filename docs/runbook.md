# Operational Runbook

This runbook describes how to operate and recover a Maci deployment.

It assumes the Terraform stack has been deployed and the system is running with API Gateway, Lambda, DynamoDB, S3, CloudWatch, and EventBridge recovery daemon resources.

---

## First checks during any incident

Run these checks first:

```bash
aws sts get-caller-identity
aws configure get region
```

Confirm:

```text
correct AWS account
correct AWS region
correct environment
```

Then check:

```text
API Gateway access logs
Request Router Lambda logs
Tool Lambda logs
Recovery Daemon Lambda logs
Step Functions executions if used
CloudWatch metrics/alarms
DynamoDB table health
Bedrock model access/errors
```

---

## Health indicators

A healthy deployment should show:

```text
normal request latency
low 4xx/5xx rate
no unexpected AccessDenied errors
audit events written
usage events written
conversation messages written
workflow states transitioning
recovery daemon processing small/expected numbers
no growing backlog of stale workflows
no unexpected open circuit breakers
```

---

## Emergency stop options

Use the smallest effective stop.

```text
1. Tool kill switch
2. Agent kill switch
3. Tenant kill switch
4. Global kill switch
5. Pause recovery daemon schedule
6. Roll back Lambda code
7. Roll back Terraform change
```

Examples:

```text
Disable account_credit globally if financial write path is suspicious.
Disable one tenant if only that tenant is triggering bad workflows.
Pause recovery daemon if it is misclassifying workflows.
```

Do not destroy infrastructure as a first response.

---

## Incident: API returns 401/403

Likely causes:

```text
JWT missing or invalid
wrong Cognito client/user pool
expired token
tenant/user mismatch
policy deny
resource ownership deny
agent suspended/revoked
kill switch open
```

Check:

```text
API Gateway authorizer logs
Request Router logs
audit event for policy_denied or identity_mismatch
agent registry status
tenant policy record
resource ownership record
kill switch table
```

---

## Incident: API returns 500

Likely causes:

```text
Lambda exception
missing environment variable
DynamoDB AccessDenied
Bedrock AccessDenied/throttling
schema validation bug
unexpected tool backend error
```

Check:

```text
Request Router Lambda logs
Tool Lambda logs
CloudWatch error metric
trace_id / request_id
audit event around failure
```

Fix the first concrete error. Do not randomly widen IAM policies.

---

## Incident: Bedrock model call fails

Common errors:

```text
AccessDeniedException
model access not enabled
invalid model identifier
region mismatch
throttling
timeout
```

Check:

```text
model ID configured in tenant policy
region
Bedrock model access in AWS console
Lambda IAM permission for Bedrock Runtime/Agent Runtime
CloudWatch logs for Bedrock Gateway
```

If throttling or repeated timeout occurs:

```text
enable/observe circuit breaker
reduce concurrency
use backoff
consider fallback/degraded response
```

---

## Incident: account_credit executed before approval

This is a critical security/business bug.

Expected behavior:

```text
account_credit without valid approval => pending_approval
no credit applied
approval bound to exact payload
```

Immediate actions:

```text
enable account_credit tool kill switch
preserve audit logs
check approval table
check idempotency table
check billing backend state
review account_credit handler
add failing regression test
```

Do not re-enable until the bug is fixed and tested.

---

## Incident: duplicate ticket or duplicate external write

Likely cause:

```text
missing idempotency key
idempotency table unavailable
retry path bypassed idempotency
recovery resumed incorrectly
```

Check:

```text
idempotency table
workflow state
conversation metadata
tool audit events
external backend write IDs
```

Fix:

```text
ensure idempotency key is generated before write
ensure retry path checks idempotency first
add regression test for crash/retry scenario
```

---

## Incident: stale workflows growing

Likely causes:

```text
Recovery daemon not scheduled
Recovery daemon IAM failure
recovery_due_index missing or broken
lease stuck due to long lease
max attempts exceeded
human review queue not processed
```

Check:

```text
EventBridge rule enabled
Recovery Daemon Lambda logs
workflow state table
recovery_due_index
recovery_owner and recovery_lease_until
recovery_attempts
conversation system_status messages
```

Actions:

```text
fix daemon IAM/config
manually invoke daemon with max_items small
escalate max-attempt workflows
review recurring failure reason
```

---

## Incident: recovery daemon double-processing

Expected protection:

```text
conditional lease prevents double claim
```

If double-processing appears:

```text
pause EventBridge rule
check DynamoDB conditional write logic
check recovery_owner / recovery_lease_until fields
check clock/TTL/backoff configuration
verify idempotency protection for resumed writes
```

---

## Incident: audit missing on deny

Denied actions are security-relevant.

Check:

```text
tool handler deny branches
AuditLogger configuration
DynamoDB audit table write permission
S3 archive permission if enabled
CloudWatch logs for audit fallback
```

Fix:

```text
audit both allow and deny branches
include denial reason
add regression test
```

---

## Incident: conversation history missing

Check:

```text
CONVERSATION_TABLE_NAME
CONVERSATION_TRANSCRIPT_BUCKET
DynamoDB table permissions
S3 PutObject permissions
request contains or generates conversation_id
ConversationStore local/DynamoDB mode
```

Remember:

```text
conversation transcript missing != audit missing
```

They are separate systems.

---

## Manual recovery process

For ambiguous/high-risk workflows:

```text
1. Locate conversation_id and workflow_id.
2. Read workflow state record.
3. Read conversation transcript.
4. Read audit events.
5. Read approval record if any.
6. Read idempotency record.
7. Check external backend state.
8. Decide: resume, mark failed_safe, or escalate.
9. Write an audit event for the operator decision.
10. Update conversation status if user/support visibility is needed.
```

Never manually execute high-risk writes without checking approval, payload hash, and idempotency.

---

## Safe cleanup

Before `terraform destroy`:

```text
confirm account and region
confirm environment is dev/lab
check Object Lock retention
check non-empty S3 buckets
check DynamoDB data needs
preserve audit logs if needed
```

Object Lock can intentionally prevent deletion.

---

## Escalation criteria

Escalate to human/security review if:

```text
cross-tenant access suspected
financial action ambiguity
approval replay suspected
audit chain inconsistency
conversation contains leaked data
kill switch was triggered unexpectedly
recovery daemon repeatedly escalates same state
```

---

## Runbook: v0.1.7 conversation and recovery checks

Use this checklist after deploying the conversation ownership and tool recovery wiring changes.

### Check 1: same-tenant conversation ownership

1. Create a conversation as user A in tenant X.
2. Try to append to the same `conversation_id` as user B in tenant X.
3. Expected result: request is denied.
4. Confirm no message from user B appears in user A's transcript.
5. Confirm an audit/security event exists if the denial path is audited.

### Check 2: trusted conversation claim cannot be overridden

1. Create a trusted context with `conversation_id = conv-a`.
2. Send a request body with `conversation_id = conv-b`.
3. Expected result: binding error or request denial.
4. Confirm the system does not write to `conv-b`.

### Check 3: real tool handlers write workflow state

Run a normal billing investigation and verify persisted workflow state transitions:

```text
CUSTOMER_LOOKUP_DONE
BILLING_CHECK_DONE
TICKET_CREATED
WAITING_FOR_APPROVAL
APPROVED
CREDIT_EXECUTED
```

The exact final state depends on where the test stops. Before human approval, `WAITING_FOR_APPROVAL` is expected. After approved credit execution, `CREDIT_EXECUTED` is expected.

### Check 4: recovery daemon classification

Create or observe stale records in these states:

```text
TICKET_CREATED
WAITING_FOR_APPROVAL
CREDIT_EXECUTED
```

Expected behavior:

```text
TICKET_CREATED -> idempotent resume path, not duplicate ticket creation
WAITING_FOR_APPROVAL -> human review required, not auto-resume
CREDIT_EXECUTED -> do not resume, never re-execute credit
```

### Check 5: account credit idempotency still holds

1. Execute account credit once with approved payload.
2. Retry the same approved payload.
3. Expected result: deduplicated success or no-op, not a second credit.
4. Retry with modified amount and same approval.
5. Expected result: approval/idempotency rejection.

