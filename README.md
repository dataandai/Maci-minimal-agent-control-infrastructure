# Maci: minimal agent control infrastructure

AWS-deployable starter product for governing Amazon Bedrock based agentic workflows with tenant policies, strict schema validation, Bedrock Guardrails, Knowledge Base isolation, Bedrock Agent Lambda tools, usage metering, audit logs, idempotent business actions, and tenant-scoped circuit breakers.

This is intentionally **not** a custom GPU pool, vLLM, AIBrix, or Kubernetes inference repo. It assumes the model layer is managed by Amazon Bedrock and focuses on the deterministic control plane around probabilistic AI systems.

## Status

Current release: **v0.1.4**. Product name: **Maci: minimal agent control infrastructure**.

This is a **deployable security-hardened foundation for governed agent systems**, not a claim that your AWS production environment is already certified or battle-tested. The primary deployment path is now **Terraform** under `infra/terraform`, because it includes the Maci hardening resources: agent registry, approval queue, S3 audit archive, billing/account-credit tools, observability and multi-environment configuration.

The older SAM template remains as a lightweight compatibility/dev starter, but it does **not** represent the complete Maci production-hardening surface. Use Terraform for the full system.

Local validation:

```text
44 passed
```

## Start here: AWS first deploy lab

For a beginner-friendly Linux flow that deploys the dev stack into your own AWS account, run:

```bash
./quickstart/linux/dev_first_deploy.sh
```

This guided flow checks prerequisites, prepares Python, runs tests, plans and applies the Terraform dev stack, seeds demo tenant policies, creates a Cognito demo user, gets a JWT token, and smoke-tests the API. It starts in safe dev mode with `enable_real_bedrock=false` and `enable_bedrock_agent=false`, so you can learn the AWS foundation before enabling real Bedrock calls.

Step-by-step version:

```bash
./quickstart/linux/00_check_prereqs.sh
./quickstart/linux/01_prepare_local_python.sh
./quickstart/linux/02_terraform_plan_dev.sh
./quickstart/linux/03_terraform_apply_dev.sh
./quickstart/linux/04_seed_demo_data_and_user.sh
./quickstart/linux/05_get_token.sh
./quickstart/linux/06_smoke_test_api.sh
```

Full lab guide: [`docs/aws-first-deploy-lab.md`](docs/aws-first-deploy-lab.md). Latest local code audit: [`docs/code-audit-v0.1.4.md`](docs/code-audit-v0.1.4.md).

Destroy the dev stack when you are done:

```bash
./quickstart/linux/99_destroy_dev.sh
```

## Product pain point

Enterprise teams are moving from GenAI pilots to agentic workflows that can answer customer questions, retrieve private knowledge, and call business tools. The blocker is no longer “can we call an LLM?” but:

- Can we prove Tenant A never accessed Tenant B's knowledge base?
- Can we stop an agent from calling billing or ticketing tools it is not allowed to use?
- Can we enforce schemas and business contracts instead of trusting free-form model output?
- Can we audit every model, tool, guardrail, and policy decision?
- Can we cap spend when user behavior causes unpredictable token usage?
- Can we make tool actions idempotent so retries do not create duplicate tickets?
- Can we shut down unsafe workflows automatically before they create operational or compliance incidents?

## Architecture

```text
Client
  |
  v
API Gateway HTTP API + Cognito/JWT authorizer
  |
  v
Lambda: request_router
  - derive tenant context only from trusted JWT claims
  - validate request with strict Pydantic schemas
  - load tenant policy from DynamoDB or local fallback
  - enforce model/tool/knowledge-base/budget rules
  - optionally retrieve tenant-scoped Knowledge Base context
  - invoke either Bedrock Converse or a Bedrock Agent alias
  - record audit + usage ledger events
  |
  +--> Amazon Bedrock Runtime / Converse API
  +--> Amazon Bedrock Agent Runtime / InvokeAgent with sessionAttributes
  +--> Amazon Bedrock Knowledge Bases through a tenant-filtered gateway boundary
  +--> Bedrock Agent Lambda action groups
          |
          +--> Lambda tool: customer_lookup
          +--> Lambda tool: ticket_creation with idempotency
  |
  v
DynamoDB: policy, audit, usage, circuit-breaker, ticket idempotency, agent registry, approvals, resource ownership, kill switches, MCP registry
CloudWatch: dashboard, EMF metrics, Lambda logs, OTel-shaped traces
Step Functions: deployable workflow skeleton for long-running governed workflows
```

## Security-hardening focus

This release implements the missing production-agent security controls from `docs/industry-best-practices-2026.md` and `docs/security-hardening.md`:

- first-class agent identity registry with active/suspended/revoked status and human custodian;
- operator kill switches at global, tenant, agent and tool scope;
- admin endpoint for agent/resource/kill-switch operations;
- MCP server provenance registry and fingerprint checks for gateway adapters;
- per-operation resource authorization, not only tool allowlisting;
- high-risk human approval workflow for financial actions;
- read-only billing check tool and high-risk account credit tool;
- tamper-evident audit direction with event hashing and optional S3 Object Lock archive;
- per-step guardrail checks for input, retrieved context and model output;
- OTel-shaped agent trace recorder and trace-to-eval export;
- deterministic state graph runtime with Pydantic v2 strict output validation and safe-stop behavior.

## What is implemented

- AWS SAM template with API Gateway, Cognito User Pool, Lambda, DynamoDB, CloudWatch dashboard, Step Functions, and optional Bedrock Agent resources.
- Trusted tenant identity extraction from API Gateway JWT claims.
- Bedrock Agent tool identity from `sessionAttributes`, not model-generated parameters.
- Strict request/tool schemas with Pydantic `extra="forbid"`.
- Per-tenant policy engine for allowed models, tools, Knowledge Bases, max tokens, and budget.
- Optional DynamoDB-backed policy store with local demo fallback.
- Audit logger that writes to DynamoDB, optionally archives hashed events to S3, and falls back to stdout locally.
- Usage ledger that records token/cost events and increments tenant spend.
- Token-based cost estimator with replaceable sample pricing config.
- Optional real Bedrock Runtime / Knowledge Base / Agent Runtime calls via feature flags.
- Tenant-scoped DynamoDB circuit breaker abstraction with TTL.
- Bedrock Agent function-response format for tool Lambdas.
- Agent identity registry and per-operation resource authorization for tool handlers.
- Idempotent ticket creation tool to prevent retry duplicates.
- Human approval workflow for high-risk `account_credit` actions.
- CloudWatch Embedded Metric Format helper.
- Adversarial tests for tenant impersonation, tool tenant override, unknown tenants, RAG isolation, resource-level tool misuse, approval flow, guardrail intervention, graph safe-stop, and idempotency.

## What is still environment-specific before real production

- Enable Bedrock model access in your target AWS region.
- Replace demo tenant policies with an onboarding/admin workflow.
- Replace synthetic tool integrations with real CRM/ticketing systems using tenant-scoped credentials.
- Decide whether to use the included Cognito pool or your existing enterprise OIDC provider.
- Provision real Knowledge Bases and update tenant policies with real KB IDs.
- Review retention, redaction, and immutable archive requirements for audit events.
- Reconcile the usage ledger with AWS billing/CUR before using it for chargeback.
- Run load tests, prompt-injection tests, failover tests, and IAM review in your account.

## Local validation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
python -m pytest
```

AWS calls are wrapped behind gateway interfaces and are intentionally mockable. Tests do not require AWS credentials.

## Deploy to AWS dev

Use the Terraform quickstart for the full Maci stack:

```bash
./quickstart/linux/dev_first_deploy.sh
```

Or run the Terraform steps manually:

```bash
cd infra/terraform
terraform init
terraform fmt -recursive
terraform validate
terraform plan -var-file=environments/dev/terraform.tfvars
terraform apply -var-file=environments/dev/terraform.tfvars
```

Then seed demo policies and agent identities:

```bash
POLICY_TABLE=$(terraform output -raw policy_table_name)
AGENT_REGISTRY_TABLE=$(terraform output -raw agent_registry_table_name)
RESOURCE_OWNERSHIP_TABLE=$(terraform output -raw resource_ownership_table_name)
python ../../scripts/seed_demo_policies.py   --table "$POLICY_TABLE"   --agent-registry-table "$AGENT_REGISTRY_TABLE" \
  --resource-ownership-table "$RESOURCE_OWNERSHIP_TABLE"   --region eu-west-1
```

The SAM template in `infra/template.yaml` is kept as a lightweight compatibility starter. It does not include the complete Maci hardening layer, so do not use it as the source of truth for production deployment.

Turn on real Bedrock calls only after model access, IAM, tenant policies, and guardrails are configured:

```hcl
enable_real_bedrock = true
```

## Repository map

```text
docs/
  business-painpoint.md             # manager/business framing
  architecture.md                   # technical architecture and implemented-vs-target matrix
  threat-model.md                   # OWASP ASI / tenant / tool risk mapping
  limitations.md                    # honest boundaries and AWS validation requirements
  production-readiness.md           # promotion gates toward real production
  security-hardening.md        # hardening summary
  documentation-audit.md       # documentation/code consistency audit
  aws-first-deploy-lab.md           # beginner-friendly Terraform lab
  terraform-deployment.md           # multi-environment Terraform guide
  aws-deployment.md                 # legacy SAM starter notes
  runbook.md                        # operational runbook
infra/
  terraform/                        # primary deployment path for Maci
  template.yaml                     # legacy/lightweight SAM starter
  step-functions/                   # ASL workflow definition
src/maci/
  schemas.py                        # strict Pydantic request/response/tool schemas
  identity.py                       # trusted JWT/sessionAttributes identity extraction
  policy_engine.py                  # deterministic tenant policy checks
  policy_store.py                   # DynamoDB/local tenant policies
  authorization.py                  # per-operation resource authorization
  resource_ownership.py            # concrete resource->tenant ownership checks
  agent_registry.py                 # first-class agent identity registry
  approval.py                       # high-risk approval records/store
  approval_review/                  # human approval API handler
  guardrails.py                     # per-step deterministic guardrail checks
  observability.py                  # OTel-shaped trace recorder and eval export
  agent_graph.py                    # deterministic graph runtime with safe-stop
  mcp_gateway.py                    # MCP policy boundary adapter
  audit.py                          # DynamoDB/S3 audit logger with event hashes
  metrics.py                        # CloudWatch EMF helper
  cost.py                           # token/model cost estimator and usage ledger
  circuit_breaker.py                # tenant breaker with DynamoDB fallback
  idempotency.py                    # idempotent ticket action support
  bedrock_gateway.py                # mockable/real Bedrock client wrapper
  request_router.py                 # Lambda entrypoint logic
  workflow_steps.py                 # Step Functions task handlers
  agent_tools/                      # Bedrock Agent Lambda action-group handlers
scripts/
  seed_demo_policies.py
  create_cognito_demo_user.py
  get_cognito_token.py
  smoke_test_api.py
tests/
  unit and adversarial tests for identity, policy, router, tools, gateway, cost,
  approval, resource authorization, guardrails, graph safe-stop and schemas
```

## Core principle

> The model can remain probabilistic; the operational boundary around it must be deterministic.

Tenant identity, tool access, model selection, Knowledge Base access, output contracts, budget checks, audit events, idempotency, and failure handling are controlled by software policy — not by prompt instructions.

## Terraform multi-environment deployment

A Terraform deployment path is available under `infra/terraform` for long-lived AWS environments. It creates Cognito, API Gateway, Lambda functions, DynamoDB tables, Step Functions, CloudWatch dashboard and baseline alarms.

```bash
cd infra/terraform
terraform init
terraform apply -var-file=environments/dev/terraform.tfvars
```

For details, see `infra/terraform/README.md` and `docs/terraform-deployment.md`.
