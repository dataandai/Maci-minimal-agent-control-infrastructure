# Conversation History Layer

Maci separates user-facing conversation history from the security audit trail.

This is a product and safety requirement.

A user or support agent wants to know:

```text
What did I ask?
What did the assistant answer?
Was a ticket created?
Is the account credit pending approval or applied?
What is the final outcome?
```

A security auditor wants to know:

```text
Which identity acted?
Which tenant was involved?
Which policy allowed or denied the tool?
Which resource was accessed?
Was approval required?
Was the operation executed?
```

These are related, but they are not the same record.

---

## Implemented module

```text
src/maci/conversation.py
```

Main types:

```text
ConversationStore
ConversationRecord
ConversationMessage
ConversationStatus
ConversationMessageType
```

---

## Conversation statuses

```text
open
waiting_for_approval
completed
failed_safe
escalated_to_human
```

---

## Message types

```text
user_message
assistant_message
tool_result_summary
approval_status
system_status
```

`system_status` messages can be marked as `visible_to_user=false`. This is used for recovery-daemon status updates that should be available to operators but not shown as normal assistant chat messages.

---

## Storage model

The implementation supports:

```text
DynamoDB: searchable conversation metadata and message index
S3: optional transcript archive
Memory mode: local tests and credential-free demos
```

Recommended AWS pattern:

```text
DynamoDB
  PK: tenant_id
  SK: CONVERSATION#<conversation_id>
  SK: CONVERSATION#<conversation_id>#MESSAGE#<timestamp>#<message_id>

S3
  tenant_id=<tenant_id>/date=<yyyy-mm-dd>/conversation_id=<conversation_id>/messages/<message_id>.json
```

---

## Conversation record

Example record:

```json
{
  "conversation_id": "conv-123",
  "tenant_id": "tenant-acme",
  "created_by_user_id": "anna.support.17",
  "agent_id": "support-billing-agent",
  "status": "open",
  "last_message_id": "msg-002",
  "transcript_s3_prefix": "tenant_id=tenant-acme/date=2026-07-04/conversation_id=conv-123/",
  "contains_pii": true,
  "legal_hold": false
}
```

---

## Message record

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
  "visible_to_user": true,
  "redaction_status": "none"
}
```

Example assistant message:

```json
{
  "conversation_id": "conv-123",
  "message_id": "msg-002",
  "request_id": "req-789",
  "tenant_id": "tenant-acme",
  "actor_type": "assistant",
  "actor_id": "support-billing-agent",
  "message_type": "assistant_message",
  "content": "A support ticket was created and the account credit request is pending approval.",
  "visible_to_user": true,
  "redaction_status": "none"
}
```

Example recovery system status:

```json
{
  "conversation_id": "conv-123",
  "message_id": "msg-003",
  "request_id": "recovery-wf-123",
  "tenant_id": "tenant-acme",
  "actor_type": "system",
  "actor_id": "maci-control-plane",
  "message_type": "system_status",
  "content": {
    "recovery_action": "escalated_to_human",
    "workflow_id": "wf-123",
    "reason": "approval-adjacent state requires human review"
  },
  "visible_to_user": false,
  "redaction_status": "redacted"
}
```

---

## What should be stored in conversation history

Store:

- user-visible user messages;
- user-visible assistant messages;
- safe tool summaries;
- ticket IDs;
- approval status;
- final outcomes;
- non-user-visible system recovery statuses for operators.

Do not store:

- hidden chain-of-thought;
- raw JWTs;
- access tokens;
- AWS credentials;
- raw authorization headers;
- unredacted secrets;
- raw backend payloads unless explicitly needed and redacted;
- cross-tenant data;
- internal policy internals not meant for the user.

---

## Transcript vs audit

The transcript explains what happened.

The audit trail proves what happened.

Example transcript line:

```text
The account credit request is waiting for human approval.
```

Example audit event:

```json
{
  "event_type": "approval_created",
  "tenant_id": "tenant-acme",
  "user_id": "anna.support.17",
  "agent_id": "support-billing-agent",
  "action": "account_credit",
  "resource_id": "cust-123",
  "amount_usd": 500,
  "payload_hash": "sha256:...",
  "status": "pending_approval"
}
```

---

## Current limitations

The foundation exists, but production systems still need to add:

- conversation list/read API endpoints;
- tenant/admin UI for conversation search;
- export/delete workflows where required;
- redaction pipeline for raw transcripts;
- retention policy enforcement;
- authorization model for who can read which conversation;
- legal hold process where required.
