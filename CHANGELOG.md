# Changelog

## v0.1.4 - provenance and deny-audit polish

- Added audit-on-deny coverage for `billing_check` tool security and resource-authorization failures.
- Added MCP manifest fingerprint computation so the gateway can verify a canonical server manifest instead of only comparing a caller-supplied fingerprint string.
- Added MCP manifest tamper test and billing deny-audit regression test.
- Expanded local validation from 42 to 44 tests.

## v0.1.3 - concurrency audit hardening

- Hardened audit hash chaining for DynamoDB-backed deployments: audit events now advance a per-tenant chain-head record with a conditional `TransactWriteItems` append, preventing hash-chain forks across concurrent Lambda execution environments.
- Added audit sequence numbers so event order can be verified alongside `previous_event_hash` and `event_hash`.
- Fixed DynamoDB-backed tenant circuit-breaker visibility for `is_open(tenant_id)` without a category by querying the tenant partition instead of returning a blind `False`.
- Added tests proving cross-logger DynamoDB audit chaining and any-category circuit-breaker visibility.
- Expanded local validation from 40 to 42 tests.

## v0.1.2 - local hardening completion

- Added operator kill-switch controls for global, tenant, agent and tool scope.
- Added a role-gated admin handler for agent lifecycle, resource ownership and kill-switch operations.
- Added MCP server provenance/fingerprint registry checks to the MCP gateway boundary.
- Added nested payload guardrail scanning for tool inputs before Pydantic validation.
- Added local audit hash chaining with `previous_event_hash` for tamper-evident event sequences.
- Added Terraform resources and environment variables for kill-switch and MCP registry tables, plus admin API wiring.
- Added seed support for demo MCP registry data.
- Expanded local adversarial/security tests from 33 to 40.

## v0.1.1 - code-audited hardening

- Added explicit resource ownership enforcement via `resource_ownership.py` and optional DynamoDB table.
- Added payload binding for high-risk approvals so approval IDs cannot be replayed with modified amounts or reasons.
- Hardened Terraform defaults: Bedrock Agent Lambda permissions now require explicit agent source ARNs; Knowledge Base wildcard access is dev-only.
- Updated quickstart seed flow to seed demo resource ownership records.
- Added adversarial tests for resource-ownership override and approval payload replay.

## v0.1.0 - Maci baseline

Initial public baseline for **Maci: minimal agent control infrastructure**.

This release provides a Terraform-first AWS foundation for governed agent systems:

- Cognito/JWT identity and tenant context propagation.
- API Gateway and Lambda request router.
- Strict Pydantic v2 request and tool schemas.
- Agent registry with active/suspended/revoked identities.
- Per-operation resource authorization for tool calls.
- Human approval workflow for high-risk account-credit actions.
- DynamoDB-backed policy, audit, usage, circuit-breaker, idempotency, agent-registry and approval state.
- Optional S3 Object Lock audit archive for tamper-evident audit retention.
- Deterministic agent graph runtime with validation, self-correction and safe-stop behavior.
- Guardrail checks for user input, retrieved context and model output.
- OTel-shaped trace records and trace-to-eval export.
- Linux quickstart scripts for first AWS deployment.
- Terraform multi-environment setup for dev, staging and prod.
- Unit and adversarial test coverage for identity, policy, tools, authorization, approval, guardrails and graph safety.

The version number is intentionally separate from the product name. The product is **Maci**, and this is its first baseline release: **v0.1.0**.
