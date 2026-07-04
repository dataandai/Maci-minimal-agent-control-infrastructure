# Security hardening implementation notes

This release moves the project from a deployable Bedrock/Lambda lab toward a real agent security control plane. It implements the key missing code paths called out in the 2026 production-ready agent checklist.

## Implemented control-plane capabilities

| Best-practice requirement | Maci implementation |
|---|---|
| First-class agent identity | `agent_registry.py` introduces `AgentIdentity`, status, human custodian, allowed tools/actions, and optional DynamoDB backing via `AGENT_REGISTRY_TABLE_NAME`. |
| Trusted identity only | API requests still derive tenant/user from Cognito/JWT; Bedrock tools still derive identity from `sessionAttributes`; tool schemas reject model-generated identity fields. |
| Runtime authorization per operation | `authorization.py` checks the exact tenant + tool + action + resource combination. `resource_ownership.py` can verify concrete resource ownership via DynamoDB and fail closed in staging/prod. |
| Agent-level least privilege | `tool_security.py` now combines tenant tool allowlist, agent allowlist, active/revoked agent status, and action-level checks. |
| Human approval for high-risk actions | `account_credit` tool creates pending approval records; `approval_review` API handler approves/rejects them using trusted human JWT roles. |
| Durable approval state | `approval.py` persists approvals in DynamoDB when `APPROVAL_TABLE_NAME` is set. Approval IDs are deterministic and approvals are bound to an exact payload hash to prevent approval replay with changed amounts/reasons. |
| Tamper-evident audit direction | `audit.py` writes audit records to DynamoDB and optionally archives hashed events to S3. Terraform adds an Object Lock enabled audit archive bucket. |
| Per-step guardrails | `guardrails.py` adds a deterministic local guardrail checker and real Bedrock guardrail boundary hook. The router checks user input, retrieved context, and model output. |
| OTel-style agent tracing | `observability.py` emits OpenTelemetry-shaped JSON spans and supports trace-to-eval-case export. |
| Deterministic agent graph runtime | `agent_graph.py` implements a structured state graph with planner/retrieval/tool/composer/validator nodes, Pydantic v2 strict validation, self-correction attempts, and safe-stop circuit breaker behavior. |
| Adversarial tests | `tests/test_hardening_security.py` covers resource-level denial, agent identity restrictions, human approval, guardrail intervention, tracing, and graph safe-stop behavior. |

## New tool surfaces

- `billing_check`: read-only billing status lookup.
- `account_credit`: high-risk financial action requiring human approval.
- `approval_review`: API Gateway/Lambda compatible approval decision endpoint.

## Remaining external validation

The code paths are implemented and unit-tested locally, but these still require validation in a real AWS account:

1. `terraform fmt`, `terraform validate`, and `terraform plan` against the target account.
2. S3 Object Lock behavior and retention mode on the audit archive bucket.
3. Bedrock model access and optional real guardrail API behavior.
4. Bedrock Agent action group wiring with real Agent IDs/Aliases.
5. IAM review for production ARNs, especially Knowledge Base and Bedrock Agent source ARNs.
6. End-to-end CloudWatch alarms and approval flow smoke tests.

## Security posture statement

This repository now implements the main local control-plane protections needed for a serious governed agent system. It should still be promoted through dev -> staging -> production with real AWS integration tests, IAM review, and red-team test cases before handling customer production data.
