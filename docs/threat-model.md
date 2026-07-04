# Threat model — Agentic control plane

This threat model maps the repository to 2026 agentic-system risks. It is intentionally focused on concrete control-plane protections, not prompt-only safety.

## Primary assets

- Tenant identity and tenant-scoped policies.
- Tenant Knowledge Base access.
- Business tools: customer lookup, ticket creation, billing check, account credit.
- Audit, usage, circuit-breaker and approval records.
- Bedrock model/agent invocation permissions.

## Core trust boundaries

1. **Client -> API Gateway**: JWT/Cognito authorizer is the identity boundary.
2. **API Gateway -> request router Lambda**: body fields are untrusted intent, not identity.
3. **request router -> Bedrock Agent**: trusted tenant/user/agent context is injected via `sessionAttributes`.
4. **Bedrock Agent -> tool Lambda**: model-generated tool parameters are untrusted and must pass strict schema + resource authorization.
5. **Tool Lambda -> business backend**: tenant-scoped credentials and per-resource authorization are required.

## OWASP Agentic Applications risk mapping

| Risk | Control implemented |
|---|---|
| Agent Goal Hijack | `guardrails.py` checks user input, retrieved context and model output; deterministic graph safe-stops on intervention. |
| Tool Misuse & Exploitation | `tool_security.py`, `authorization.py`, and `resource_ownership.py` enforce tenant, agent, tool, action and concrete resource boundaries in each handler. |
| Agent Identity & Privilege Abuse | `agent_registry.py` models first-class agent identities with status, human custodian, tools/actions and tenant binding. |
| Agentic Supply Chain Compromise | `mcp_gateway.py` is only a centralized per-operation enforcement adapter for future MCP integrations. Full ASI04 mitigation still requires MCP server provenance, dependency scanning, signed releases and gateway deployment controls. |
| Rogue Agent | `REQUIRE_AGENT_ID`, agent status checks and kill-switch/circuit-breaker state provide containment controls. |
| Cross-tenant data exposure | Tenant context comes from JWT/session attributes and resource IDs are checked against tenant policy. |
| High-risk action without approval | `account_credit` requires human approval through `approval.py` and `approval_review.handler`. |

## Lethal trifecta handling

The architecture separates:

- private tenant data: Knowledge Base and backend tool results;
- untrusted content: user input and retrieved text;
- outbound action: tool calls and final responses.

Guardrail checks and policy gates are placed before crossing from one category into another. High-risk outbound actions require explicit approval.

## Required production review

Before production use, run:

- AWS IAM review for concrete ARNs;
- Terraform plan review;
- red-team tests for prompt injection and tool abuse;
- audit-retention and PII-redaction review;
- human approval/MFA review for high-risk actions.
