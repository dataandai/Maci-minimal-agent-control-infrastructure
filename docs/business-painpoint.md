# Business Painpoint: Governed AI Support Agent for Multi-Tenant SaaS

## Manager persona

**Name:** Maya Ben-David  
**Role:** VP Customer Operations / AI Transformation Lead  
**Company type:** B2B SaaS or fintech platform serving enterprise customers  
**Team:** 80 support agents, 12 implementation consultants, 5 compliance/risk stakeholders, shared platform engineering team  
**Goal:** Use GenAI to reduce support load and improve customer response time without creating compliance, tenant isolation, or uncontrolled-cost risks.

## The real pain

Maya's company already has several GenAI pilots:

- A customer support chatbot that answers from documentation.
- An internal support copilot that summarizes tickets.
- A prototype agent that can look up customer status and create tickets.
- A small RAG pipeline over product docs and onboarding guides.

The pilots are useful, but they cannot be rolled out to enterprise customers because the risk team keeps blocking them.

The objections are not about model quality alone. The objections are about **operational control**:

1. **Cross-tenant data leakage risk**  
   One enterprise customer must never retrieve another tenant's documents, ticket summaries, billing records, or user profile data.

2. **Uncontrolled tool execution**  
   A model must not decide freely that it can call billing, CRM, refunds, customer lookup, or ticket creation tools. Tool access must be tenant-scoped, role-scoped, and auditable.

3. **No audit trail**  
   Compliance needs to know which model was used, what knowledge base was queried, which tool was called, what policy allowed/denied it, and what happened when validation failed.

4. **Schema drift and hallucinated actions**  
   Free-form model output breaks downstream automation. The support system requires deterministic fields such as `customer_id`, `ticket_priority`, `action_type`, and `allowed_next_steps`.

5. **Unpredictable cost**  
   Model usage is charged by tokens. Long customer conversations, verbose prompts, and retry loops can create unexpected cost spikes without per-tenant budgets and stop conditions.

6. **Governance gap between demo and production**  
   The company can build prompt chains quickly, but it lacks a reusable control plane for identity, policy, guardrails, observability, and circuit breakers.

## Business outcome the system targets

The proposed system allows Maya to say yes to AI automation while giving risk and engineering deterministic controls.

Target outcomes:

- Reduce repetitive Tier-1 support workload.
- Improve first response time for enterprise customers.
- Keep tenant data isolated by design.
- Provide audit-grade logs for model, tool, retrieval, and policy decisions.
- Prevent unauthorized tool actions.
- Cap usage and stop runaway workflows.
- Make AI support rollout repeatable across tenants.

## Why Bedrock + Lambda is a good fit

This organization does not want to operate its own model-serving infrastructure. It wants managed foundation models, AWS-native security boundaries, serverless scaling, and clear ownership.

The chosen architecture uses:

- **Amazon Bedrock** for managed model access.
- **Bedrock Guardrails** for safety and privacy controls.
- **Bedrock Knowledge Bases** for managed RAG over private documents.
- **Lambda** for policy enforcement and business tool execution.
- **Step Functions** for multi-step workflows, retries, and circuit-breaker branches.
- **DynamoDB** for tenant policies and audit metadata.
- **CloudWatch / OpenTelemetry-style trace fields** for observability.

## Product requirements

### Functional requirements

- Accept a support request from a tenant user.
- Verify/derive tenant context from trusted identity claims.
- Validate the request body using strict schemas.
- Load tenant policy.
- Check allowed model, tool, knowledge base, max tokens, and budget.
- Call Bedrock only after policy approval.
- Retrieve tenant-scoped context only from approved knowledge bases.
- Execute only allowlisted Lambda tools.
- Validate all tool inputs and outputs.
- Emit audit events for every decision.
- Trip a circuit breaker after repeated validation, tool, budget, or policy failures.

### Non-functional requirements

- No cross-tenant data access.
- All decisions must be explainable through logs.
- AWS calls must be mockable for tests.
- Local tests must not require AWS credentials.
- The architecture must be deployable through infrastructure-as-code.
- The system must fail closed by default.

## KPIs

- 0 cross-tenant knowledge-base access incidents.
- 100% policy-decision logging coverage for production requests.
- 100% schema validation on tool inputs/outputs.
- Reduction in Tier-1 manual ticket handling.
- Lower mean first response time.
- Per-tenant monthly AI spend remains within configured budget.
- Circuit breaker activates before repeated unsafe/retry loops exceed configured threshold.

## Scope boundary

This repo solves the **governance/control-plane problem**, not the model-hosting problem.

It intentionally does not include:

- GPU scheduling.
- Custom model training.
- Fine-tuning pipelines.
- Full billing reconciliation.
- A real CRM integration.
- A complete enterprise IAM rollout.

Those are future production integrations, not required for the reference architecture.
