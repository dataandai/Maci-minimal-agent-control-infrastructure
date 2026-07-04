# Code audit v0.1.2

This release closes the remaining locally implementable hardening gaps that do not require a live AWS account.

## Implemented in code

- **Operator kill switches**: `kill_switch.py` supports global, tenant, agent and tool scopes. The request router checks kill switches before model work, and every tool invocation checks the relevant tool/agent/tenant scope through `tool_security.py`.
- **Admin API boundary**: `admin/handler.py` provides a strict, role-gated control-plane handler for agent lifecycle changes, resource ownership onboarding, and kill-switch enable/clear operations.
- **MCP provenance checks**: `mcp_registry.py` models allowlisted MCP server provenance and expected fingerprints. `mcp_gateway.py` now refuses server-backed tool calls when the fingerprint or tenant binding does not match.
- **Nested tool-input guardrails**: `guardrails.py` now scans nested payload strings, and all tool handlers enforce this before Pydantic validation and business authorization.
- **Audit hash chaining**: `audit.py` adds `previous_event_hash` and maintains a local per-tenant hash chain so sequential local audit events are tamper-evident. S3 Object Lock remains the AWS archive path.
- **Terraform wiring**: Terraform now includes kill-switch and MCP registry tables, an admin Lambda, `/admin/control-plane` API route, and relevant environment variables.
- **Seed data**: `scripts/seed_demo_policies.py` can seed demo MCP server registry records.

## Locally validated

```text
40 passed
python compileall OK
quickstart bash syntax OK
```

## Still requires AWS validation

- Terraform `fmt`, `validate`, `plan`, and `apply` in a real environment.
- Cognito/OIDC JWT claims and admin role mapping.
- Bedrock model, Agent, Knowledge Base and Guardrails integration.
- S3 Object Lock retention behavior and CloudWatch alarm behavior.
- Real CRM/ticketing/billing backend integrations.


## Superseded by v0.1.3

The local-only hash chain described above was replaced in `docs/code-audit-v0.1.3.md` with a DynamoDB chain-head + conditional transaction append design for concurrent Lambda safety.
