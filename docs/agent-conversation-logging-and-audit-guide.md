# Agent Conversation Logging and Audit Guide

This guide explains how to store agent conversations, audit events, operational logs, and usage records in a production-style governed AI agent system.

The key idea:

> Do not treat all logs as the same thing.

A user-facing conversation history, a security audit trail, operational debug logs, and a cost ledger have different purposes, retention rules, access controls, and privacy risks.

---

## 1. Why This Matters

Users, support teams, engineers, and auditors may all need to understand what happened during an agent workflow.

Common questions include:

```text
What did the user ask?
What did the agent answer?
Which tool did the agent request?
Was the tool allowed or denied?
Which customer record was accessed?
Was the action executed or only requested?
Who approved a high-risk action?
Why was an action blocked?
How much did the workflow cost?
Can we reconstruct this incident later?
```

A PoC agent may not store much.

A product agent system needs structured logging by design.

---

## 2. Use Four Separate Logging Layers

Use four separate layers:

```text
1. Conversation transcript
2. Security audit trail
3. Operational logs and traces
4. Usage and cost ledger
```

They should share IDs such as `request_id`, `conversation_id`, `trace_id`, and `tenant_id`, but they should not be collapsed into one unstructured log.

---

## 3. Conversation Transcript

The conversation transcript is the user-facing or support-facing history.

It is useful for:

```text
showing the user what happened
resuming a support case
reviewing agent behavior
exporting conversation history
debugging product UX
```

It may contain:

```text
user message
assistant response
safe tool result summary
approval status
ticket ID
final outcome
```

It should not contain:

```text
AWS credentials
raw JWT claims
raw authorization headers
backend secrets
full internal policy rules
hidden model chain-of-thought
debug stack traces
unredacted cross-tenant data
```

The transcript explains what happened to the user.

It is not a full security audit trail.

---

## 4. Security Audit Trail

The security audit trail records security-relevant and business-relevant decisions.

It should answer:

```text
Who acted?
Which tenant was involved?
Which agent was involved?
Which tool was requested?
Was it allowed or denied?
Which policy decision was made?
Which resource was accessed?
Was human approval required?
Was the action executed?
Was a guardrail triggered?
Was a kill switch or circuit breaker involved?
```

Audit records should be append-only or tamper-evident where appropriate.

High-risk business actions such as account credit should always be audited.

Denied actions should also be audited.

---

## 5. Operational Logs and Traces

Operational logs are for engineers and operators.

They help answer:

```text
Why did the Lambda fail?
Did Bedrock throttle the request?
Did DynamoDB reject a conditional write?
Did the API authorizer fail?
Did the circuit breaker open?
Which downstream system timed out?
```

Operational logs usually go to CloudWatch Logs or an observability backend.

They should be redacted and have explicit retention.

Do not dump full raw conversations into operational logs.

---

## 6. Usage and Cost Ledger

The usage ledger records cost and metering data.

It should track:

```text
tenant_id
agent_id
request_id
model_id
input_tokens
output_tokens
tool_calls
retrieval_calls
validation_retries
guardrail_interventions
estimated_cost
timestamp
```

The usage ledger should usually avoid storing full conversation text.

It is for cost control, billing, budget checks, and operational reporting.

---

## 7. Recommended AWS Storage Pattern

A practical AWS pattern:

```text
DynamoDB
  - conversation metadata
  - message index
  - approval state
  - usage ledger
  - audit metadata
  - circuit breaker state

S3
  - full conversation transcript objects
  - archived audit event batches
  - redacted tool result snapshots if needed

CloudWatch Logs
  - Lambda logs
  - API Gateway logs
  - Step Functions logs
  - operational errors

CloudWatch / X-Ray / OpenTelemetry
  - traces
  - metrics
  - latency
  - workflow spans

KMS
  - encryption keys

IAM
  - tenant-scoped and role-scoped access controls
```

A good rule:

```text
DynamoDB stores searchable metadata.
S3 stores larger transcript/audit objects.
CloudWatch stores operational logs.
```

---

## 8. Example Transcript Storage

A transcript can be stored as JSON Lines in S3.

Example S3 key:

```text
s3://agent-conversation-archive/
  tenant_id=tenant-acme/
  date=2026-07-04/
  conversation_id=conv-123/
  transcript.jsonl
```

Example user message:

```json
{
  "conversation_id": "conv-123",
  "message_id": "msg-001",
  "request_id": "req-789",
  "tenant_id": "tenant-acme",
  "actor_type": "user",
  "actor_id": "anna.support.17",
  "message_type": "user_message",
  "content": "Check billing for customer cust-123 and request credit if needed.",
  "created_at": "2026-07-04T10:15:00Z",
  "redaction_status": "none"
}
```

Example assistant response:

```json
{
  "conversation_id": "conv-123",
  "message_id": "msg-002",
  "request_id": "req-789",
  "tenant_id": "tenant-acme",
  "actor_type": "assistant",
  "actor_id": "support-billing-agent",
  "message_type": "assistant_message",
  "content": "A possible overcharge was found. A support ticket was created and the account credit request is pending approval.",
  "created_at": "2026-07-04T10:15:12Z",
  "redaction_status": "none"
}
```

Example safe tool summary:

```json
{
  "conversation_id": "conv-123",
  "message_id": "msg-003",
  "request_id": "req-789",
  "tenant_id": "tenant-acme",
  "actor_type": "tool",
  "actor_id": "billing_check",
  "message_type": "tool_result_summary",
  "content": {
    "invoice_id": "inv-789",
    "status": "possible_overcharge",
    "overcharge_amount_usd": 500
  },
  "created_at": "2026-07-04T10:15:09Z",
  "redaction_status": "redacted"
}
```

Do not store every raw backend payload unless it is necessary.

---

## 9. Example Conversation Metadata Table

DynamoDB can store searchable conversation metadata.

Example table:

```text
agent_conversations
```

Example key:

```text
PK = TENANT#tenant-acme
SK = CONVERSATION#conv-123
```

Example item:

```json
{
  "tenant_id": "tenant-acme",
  "conversation_id": "conv-123",
  "created_by": "anna.support.17",
  "agent_id": "support-billing-agent",
  "status": "completed",
  "created_at": "2026-07-04T10:15:00Z",
  "updated_at": "2026-07-04T10:16:00Z",
  "transcript_s3_key": "tenant_id=tenant-acme/date=2026-07-04/conversation_id=conv-123/transcript.jsonl",
  "retention_until": "2026-10-04T00:00:00Z",
  "contains_pii": true,
  "legal_hold": false
}
```

This lets the UI list conversations without scanning S3.

---

## 10. Do Not Store Hidden Chain-of-Thought

Do not store hidden model chain-of-thought as a user-facing artifact.

Store structured decision traces instead.

Bad:

```text
Full hidden model reasoning text.
```

Better:

```json
{
  "decision_trace": [
    {
      "step": "customer_lookup",
      "reason_code": "billing_investigation_requires_customer_context",
      "status": "allowed"
    },
    {
      "step": "billing_check",
      "reason_code": "customer_reported_possible_overcharge",
      "status": "allowed"
    },
    {
      "step": "account_credit",
      "reason_code": "billing_check_indicated_possible_overcharge",
      "status": "pending_approval"
    }
  ]
}
```

This provides explanation without storing private reasoning text.

---

## 11. Tool Call Logging

Every tool call should produce two different records:

```text
1. Conversation-safe summary
2. Security audit event
```

Conversation-safe summary:

```json
{
  "message_type": "tool_result_summary",
  "tool": "billing_check",
  "summary": "Possible overcharge detected for July invoice.",
  "visible_to_support_user": true
}
```

Security audit event:

```json
{
  "event_type": "tool_allowed",
  "tenant_id": "tenant-acme",
  "user_id": "anna.support.17",
  "agent_id": "support-billing-agent",
  "tool": "billing_check",
  "resource_type": "customer",
  "resource_id": "cust-123",
  "policy_decision": "allow",
  "decision_reason": "support_agent_can_read_billing_for_owned_customer",
  "request_id": "req-789",
  "timestamp": "2026-07-04T10:15:09Z"
}
```

The transcript tells the user what happened.

The audit event proves why it was allowed.

---

## 12. Denied Actions Must Be Logged

Denied actions are security-relevant.

Example audit event:

```json
{
  "event_type": "tool_denied",
  "tenant_id": "tenant-acme",
  "user_id": "anna.support.17",
  "agent_id": "support-billing-agent",
  "tool": "customer_lookup",
  "resource_type": "customer",
  "resource_id": "contoso-001",
  "policy_decision": "deny",
  "decision_reason": "resource_not_owned_by_tenant",
  "request_id": "req-790",
  "timestamp": "2026-07-04T10:20:00Z"
}
```

User-facing version:

```text
The requested customer record could not be accessed from this tenant.
```

Do not expose internal policy details unless the user is authorized to see them.

---

## 13. Human Approval Logging

High-risk actions should create explicit approval records.

Approval created:

```json
{
  "event_type": "approval_created",
  "approval_id": "appr-999",
  "tenant_id": "tenant-acme",
  "requested_by": "anna.support.17",
  "agent_id": "support-billing-agent",
  "action": "account_credit",
  "resource_id": "cust-123",
  "amount_usd": 500,
  "payload_hash": "sha256:...",
  "status": "pending_approval",
  "timestamp": "2026-07-04T10:15:15Z"
}
```

Approval approved:

```json
{
  "event_type": "approval_approved",
  "approval_id": "appr-999",
  "tenant_id": "tenant-acme",
  "approved_by": "bela.risk.04",
  "action": "account_credit",
  "resource_id": "cust-123",
  "amount_usd": 500,
  "payload_hash": "sha256:...",
  "timestamp": "2026-07-04T10:18:00Z"
}
```

The approval must be tied to the exact operation payload.

An approval for one amount, customer, tenant, or action must not be reusable for another.

---

## 14. Redaction Rules

Redact or avoid storing:

```text
access tokens
refresh tokens
API keys
passwords
session cookies
authorization headers
payment card data
bank account details
national IDs
unnecessary personal data
raw backend credentials
```

Example:

```text
Authorization: Bearer eyJhbGci...
```

should become:

```text
Authorization: [REDACTED]
```

Use stable hashes where needed for correlation.

---

## 15. Retention Strategy

Different records need different retention periods.

Example development environment:

```text
Operational logs: 7-14 days
Conversation transcripts: 30-90 days
Usage records: 90-180 days
Security audit: 180-365 days
High-risk action audit: depends on business/legal needs
```

Do not keep everything forever by default.

CloudWatch Logs can keep logs indefinitely unless retention is configured.

DynamoDB TTL can help automatically expire records.

S3 Object Lock can protect important audit records, but it must be used carefully because retained objects may not be deletable until retention conditions are satisfied.

---

## 16. Access Control

Different users need different access.

Example:

```text
Support user:
  Can view conversations for their tenant and assigned cases.

Tenant admin:
  Can view tenant-level conversation history.

Risk approver:
  Can view approval-related conversation context.

Engineer/operator:
  Can view redacted operational logs.

Security auditor:
  Can view audit events.

End user:
  Can view their own conversation where appropriate.
```

Avoid broad access to raw logs.

Logs often contain sensitive business and user context.

---

## 17. Shared IDs

Use shared IDs to connect layers.

Recommended IDs:

```text
request_id
conversation_id
message_id
tenant_id
user_id
agent_id
tool_call_id
approval_id
trace_id
audit_event_id
resource_id
```

This lets you reconstruct a workflow without duplicating sensitive content everywhere.

---

## 18. Example End-to-End Timeline

A normal billing investigation may produce:

```text
1. User logs in.
2. Conversation is created.
3. User message is stored.
4. Tenant context is created.
5. Policy pre-check is audited.
6. Input guardrail result is audited.
7. Agent planning starts.
8. Customer lookup is requested.
9. Customer lookup is authorized.
10. Customer lookup summary is stored.
11. Billing check is requested.
12. Billing check is authorized.
13. Billing summary is stored.
14. Ticket is created.
15. Account credit is requested.
16. Approval is created.
17. Transcript says credit is pending approval.
18. Risk approver approves the request.
19. Account credit executes.
20. Final assistant response is stored.
21. Usage cost is recorded.
22. Trace is closed.
```

---

## 19. Example User-Facing History

The user or support user may see:

```text
User:
Check billing for customer cust-123. If there was an overcharge, create a ticket and request account credit.

Assistant:
I found the customer record and checked the July invoice. There appears to be a possible 500 USD overcharge.

Assistant:
A support ticket was created: ticket-456.

Assistant:
An account credit request was created and is waiting for human approval.

Risk Approver:
Approved the 500 USD account credit request.

Assistant:
The 500 USD account credit has been applied.
```

This is useful for humans.

It is not enough for security auditing.

---

## 20. Example Security Audit Timeline

The audit trail may contain:

```text
identity_bound
conversation_created
policy_precheck_allowed
input_guardrail_passed
tool_requested: customer_lookup
tool_allowed: customer_lookup
resource_ownership_passed
tool_executed: customer_lookup
tool_requested: billing_check
tool_allowed: billing_check
tool_executed: billing_check
tool_requested: ticket_creation
tool_allowed: ticket_creation
tool_executed: ticket_creation
tool_requested: account_credit
approval_required
approval_created
approval_approved
account_credit_executed
final_response_validated
```

This is useful for security, compliance, and incident review.

It is too detailed for most end users.

---

## 21. Minimal Implementation Checklist

A minimal implementation should include:

```text
Conversation metadata table
Transcript storage location
Audit event writer
Usage ledger writer
CloudWatch log retention
Redaction utility
Shared request_id / conversation_id / trace_id
Tenant-scoped access model
Retention policy
Export/delete strategy where required
Denied-action audit logging
Approval audit logging
```

---

## 22. Final Summary

Yes, agent conversations should be stored, but carefully.

The user-facing transcript explains what happened.

The audit trail proves what happened.

Operational logs help engineers debug what happened.

The usage ledger shows what it cost.

These are related, but they are not the same thing.

A production system should record:

```text
who made the request
which tenant was involved
which tool was requested
which resource was accessed
which policy decision was made
whether approval was required
whether the action actually executed
how much the workflow cost
how the event can be reconstructed later
```

The LLM can remain probabilistic.

Logging, audit, retention, and access control must be deterministic.

---

## 23. Useful References

- Amazon CloudWatch Logs:
  - https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/WhatIsCloudWatchLogs.html
  - https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/Working-with-log-groups-and-streams.html

- Amazon DynamoDB TTL:
  - https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html

- Amazon S3 Object Lock:
  - https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html

- GDPR Article 5 principles:
  - https://gdpr-info.eu/art-5-gdpr/

- UK ICO storage limitation guidance:
  - https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/data-protection-principles/a-guide-to-the-data-protection-principles/storage-limitation/
