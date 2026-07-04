# Code audit v0.1.1

This audit is a code-level follow-up to the documentation review. The goal is to ensure the repository does not rely on documentation claims for critical security controls.

## What was verified locally

- Python unit/adversarial tests: `33 passed`.
- Python compilation: `python -m compileall` passed for `src`, `tests`, and `scripts`.
- Linux quickstart shell syntax: `bash -n quickstart/linux/*.sh` passed.
- Markdown relative links were checked in the previous documentation audit path and remain valid after the v0.1.1 edits.

## Fixes added after the code audit

### 1. Concrete resource ownership enforcement

`ResourceAuthorizer` now calls `ResourceOwnershipStore` before falling back to prefix-based dev behavior. Production/staging should set:

```hcl
require_resource_ownership = true
```

This prevents a semantically valid but cross-tenant-looking resource ID from being authorized only because it matches a broad prefix.

### 2. Approval payload binding

High-risk approvals now include a payload hash. `account_credit` rejects an approval ID if it was approved for a different amount, reason, customer, or payload shape.

### 3. Terraform IAM hardening

Action-group Lambda invoke permissions are no longer created with a default `agent/*` source ARN. Terraform now creates Bedrock service-principal permissions only for explicit `allowed_bedrock_agent_source_arns`.

### 4. Dev-only Knowledge Base wildcard

Knowledge Base wildcard IAM access is now restricted to beginner dev lab mode. Staging/prod should set concrete `allowed_knowledge_base_arns`.

## Remaining external validation

This sandbox does not include Terraform, so the following must still be run in the target toolchain:

```bash
terraform -chdir=infra/terraform fmt -recursive
terraform -chdir=infra/terraform init -backend=false
terraform -chdir=infra/terraform validate
terraform -chdir=infra/terraform plan -var-file=environments/dev/terraform.tfvars
```

Real AWS validation is also required for Cognito token issuance, API Gateway JWT authorization, Lambda packaging, DynamoDB table IAM, Bedrock model access, and Bedrock Agent action-group wiring.


## Historical note

This file records the previous code-audit release. The latest local hardening audit is `docs/code-audit-v0.1.4.md`.
