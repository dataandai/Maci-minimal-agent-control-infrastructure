# Limitations

This document states what Maci does not prove yet.

The goal is to keep the repository honest.

---

## Current honest status

Maci v0.1.6 is a locally verified, AWS-deployable foundation.

It includes code and tests for:

- trusted identity boundaries;
- strict schemas;
- tenant policy checks;
- resource ownership;
- approval flow;
- audit and usage ledgers;
- conversation history foundation;
- workflow state;
- idempotency;
- recovery daemon foundation;
- circuit breakers and kill switches.

It does not prove your AWS production environment is ready.

---

## Terraform not proven by local tests

Python tests do not validate live AWS deployment.

You must run in the target AWS account:

```bash
terraform -chdir=infra/terraform fmt -recursive
terraform -chdir=infra/terraform init
terraform -chdir=infra/terraform validate
terraform -chdir=infra/terraform plan -var-file=environments/dev/terraform.tfvars
terraform -chdir=infra/terraform apply -var-file=environments/dev/terraform.tfvars
```

Potential AWS-only failures:

- missing IAM permissions;
- region mismatch;
- Bedrock model access missing;
- S3 bucket name conflict;
- Object Lock constraints;
- DynamoDB index limits;
- Lambda package path issues;
- API Gateway authorizer configuration issues;
- service quotas.

---

## Bedrock access is environment-specific

The repository cannot prove:

- your account has access to the selected model;
- the model exists in your chosen region;
- Bedrock Guardrails/Knowledge Bases/Agent aliases are configured;
- your Lambda roles have exact runtime permissions;
- latency and throttling are acceptable.

---

## Conversation history is a foundation, not a finished product UI

Implemented:

- `ConversationStore`;
- `conversation_id` / `message_id`;
- DynamoDB metadata/message index pattern;
- optional S3 transcript archive;
- user/assistant/system-status message types.

Still needed for a product:

- conversation list/read API;
- user/support/admin UI;
- tenant-scoped access-control enforcement on read APIs;
- export/delete workflows;
- legal hold workflow;
- redaction pipeline;
- retention enforcement.

---

## Recovery daemon is a foundation, not a complete orchestrator

Implemented:

- due-record scan;
- GSI pattern;
- lease-based claim;
- resume classification;
- retry/backoff;
- human escalation;
- recovery audit/status messages.

Still needed for production:

- integration with your selected orchestrator resume mechanism;
- Step Functions redrive/resume strategy if used;
- queue/task dispatch for resumed work;
- operator UI for escalated workflows;
- backend reconciliation for ambiguous external writes;
- chaos testing.

The daemon intentionally does not directly execute high-risk actions.

---

## MCP scope is limited

The MCP registry/provenance code is a policy-boundary foundation.

It is not a complete MCP transport server.

Still needed:

- full MCP server/client transport;
- server signing or stronger attestation if required;
- dependency/SCA process;
- runtime credential boundary;
- per-operation policy enforcement around actual MCP calls.

---

## Audit is not a compliance certificate

Maci provides audit foundations:

- audit events;
- allow/deny logging;
- event hashes;
- DynamoDB chain-head concurrency hardening;
- optional S3 Object Lock archive.

Your organization must still define:

- retention policy;
- legal hold policy;
- deletion/export policy;
- access controls;
- compliance mapping;
- monitoring and review process.

---

## Tool integrations are demos/stubs

The current tools model the boundaries:

- customer lookup;
- billing check;
- ticket creation;
- account credit approval.

Real deployments must replace demo integrations with real tenant-scoped CRM/ticketing/billing systems and credentials.

---

## No production load guarantee

The repository does not prove:

- high concurrency behavior in your account;
- Bedrock throttling behavior;
- DynamoDB hot partition behavior;
- S3/KMS throughput;
- Lambda cold-start impact;
- cost under real workloads.

Run load and chaos tests.

---

## LLM correctness is not guaranteed

Maci controls execution boundaries.

It does not guarantee that the model always:

- interprets the customer issue correctly;
- chooses the optimal next step;
- writes the best final answer;
- avoids all hallucinations.

Output validation, guardrails, tool results, and human review reduce risk. They do not make model reasoning perfect.
