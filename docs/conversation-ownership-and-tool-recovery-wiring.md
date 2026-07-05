# Conversation Ownership and Tool Recovery Wiring

This document explains the v0.1.7 hardening pass that fixed two issues found during code review of the conversation and recovery foundation.

The fixes matter because both issues affected the same production principle:

> A resumable resource must have an owner, and a recoverable workflow must persist real state transitions from the real execution path.

---

## 1. Problem fixed: real tool states were not persisted

The recovery daemon introduced durable workflow states such as:

```text
CUSTOMER_LOOKUP_DONE
BILLING_CHECK_DONE
TICKET_CREATED
WAITING_FOR_APPROVAL
APPROVED
CREDIT_EXECUTED
```

The recovery scanner could classify these states correctly, but in v0.1.6 most of these states were only produced by tests or synthetic records.

The real tool handlers did not consistently update the persistent workflow record.

That meant a real workflow could look like this after a crash:

```text
PLANNING_STARTED
```

while the business flow had actually progressed further, for example:

```text
billing check completed
ticket created
account credit approval pending
```

That is dangerous because the recovery daemon could classify the record too optimistically.

---

## 2. v0.1.7 behavior: tool handlers write durable state

v0.1.7 wires workflow state updates into the real tool handlers.

Expected transitions:

```text
customer_lookup   -> CUSTOMER_LOOKUP_DONE
billing_check     -> BILLING_CHECK_DONE
ticket_creation   -> TICKET_CREATED
account_credit    -> WAITING_FOR_APPROVAL
account_credit    -> APPROVED
account_credit    -> CREDIT_EXECUTED
```

This means the recovery daemon no longer operates only on synthetic test states. It sees the durable state produced by the actual agent tool path.

---

## 3. Recovery impact

The recovery daemon classifies workflow records according to the persisted state.

Examples:

```text
CUSTOMER_LOOKUP_DONE     -> AUTO_RESUME
BILLING_CHECK_DONE       -> AUTO_RESUME
TICKET_CREATED           -> IDEMPOTENT_RESUME
WAITING_FOR_APPROVAL     -> HUMAN_REVIEW_REQUIRED
APPROVED                 -> HUMAN_REVIEW_REQUIRED or guarded idempotent path
CREDIT_EXECUTED          -> DO_NOT_RESUME
```

The exact classification may depend on implementation details, but the principle is stable:

- read-only completed states can usually resume safely;
- write-adjacent states require idempotency;
- approval-adjacent and financial states require human review or strict payload-bound idempotency;
- completed high-risk execution must not run twice.

---

## 4. Problem fixed: `conversation_id` was resumable but not owner-checked

The tenant boundary was already protected, but a user inside the same tenant could provide another user's known or guessed `conversation_id` and append messages to that conversation.

This was not a cross-tenant bug, but it was still an ownership bug.

A conversation is a resource.

Therefore, resuming a conversation must be treated like accessing any other resource:

```text
same tenant is necessary
same authorized owner/reader is also required
```

---

## 5. v0.1.7 behavior: conversation resume is ownership-checked

v0.1.7 applies the same ownership pattern to conversations.

The system now enforces:

```text
1. request body conversation_id cannot override a trusted conversation claim;
2. existing conversation records must belong to the authenticated user before resume;
3. new conversation records are created conditionally;
4. same-tenant races on guessable conversation IDs cannot silently overwrite ownership;
5. trusted conversation_id is propagated through router context and Bedrock sessionAttributes.
```

This prevents a same-tenant user from appending to another user's transcript simply by reusing the same `conversation_id`.

---

## 6. Correct mental model

The old mistake would be:

```text
conversation_id is just a correlation ID
```

The correct model is:

```text
conversation_id is a tenant-scoped, owner-checked resource identifier
```

A request may refer to a conversation, but the system decides whether that user is allowed to resume it.

---

## 7. Request binding rule

When a trusted conversation claim exists, the request body must not override it.

Conceptual rule:

```text
if request.conversation_id is present
and tenant_context.conversation_id is present
and request.conversation_id != tenant_context.conversation_id:
    reject request
```

This mirrors the existing rule for tenant/user identity binding.

---

## 8. Conversation store resume rule

When resuming an existing conversation, the store must check ownership before appending messages.

Conceptual rule:

```text
existing = load_conversation(tenant_id, conversation_id)

if existing.created_by_user_id != tenant_context.user_id:
    reject resume
```

More advanced production systems may support shared case assignment or team-based conversation access, but that must be explicit policy, not accidental ID reuse.

---

## 9. Required regression tests

The v0.1.7 test suite should prove:

```text
same-tenant user cannot resume another user's conversation
body conversation_id cannot override trusted conversation claim
customer_lookup writes CUSTOMER_LOOKUP_DONE
billing_check writes BILLING_CHECK_DONE
ticket_creation writes TICKET_CREATED with idempotency context
account_credit writes WAITING_FOR_APPROVAL before approval
account_credit writes CREDIT_EXECUTED only after guarded execution
```

These tests prevent the same bug pattern from returning when new resumable resources are added.

---

## 10. Production boundary

This hardening improves local correctness, but AWS runtime validation is still required.

Before relying on this in an AWS environment, run:

```text
unit tests
integration tests
Terraform validate/plan
AWS dev smoke tests
cross-tenant denial tests
same-tenant conversation ownership tests
recovery daemon smoke tests
approval replay tests
```

The local code can prove the control logic.

The target AWS account must still prove IAM, DynamoDB, Lambda, API Gateway, Bedrock, EventBridge, S3, and CloudWatch behavior.
