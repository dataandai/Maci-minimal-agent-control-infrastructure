# Terraform Deployment

Terraform is the primary deployment path for the full Maci system.

The SAM template is retained for lightweight/dev compatibility, but Terraform is the source of truth for the complete hardening surface.

---

## What Terraform deploys

Depending on variables, the Terraform stack includes:

```text
API Gateway / HTTP API
Cognito/JWT authorizer resources
Request Router Lambda
Tool Lambdas
Approval handler Lambda
Recovery Daemon Lambda
EventBridge recovery schedule
DynamoDB tables
S3 audit archive bucket
S3 conversation transcript bucket
CloudWatch logs/metrics/dashboard resources
Step Functions workflow skeleton
IAM roles and policies
```

State tables include patterns for:

```text
policy
audit
usage
circuit breaker
ticket idempotency
generic idempotency
workflow state
conversation metadata/messages
agent registry
approval
resource ownership
kill switch
MCP registry
```

---

## Basic commands

```bash
cd infra/terraform
terraform init
terraform fmt -recursive
terraform validate
terraform plan -var-file=environments/dev/terraform.tfvars
terraform apply -var-file=environments/dev/terraform.tfvars
```

For CI validation without a backend:

```bash
terraform -chdir=infra/terraform init -backend=false
terraform -chdir=infra/terraform validate
```

---

## Before running apply

Check:

```bash
aws sts get-caller-identity
aws configure get region
```

Confirm:

```text
correct AWS account
correct AWS region
correct Terraform workspace/state
Bedrock model access strategy
S3 bucket naming
Object Lock/retention intent
```

---

## Plan review checklist

Review the plan for:

```text
DynamoDB table creation/replacement
S3 bucket creation/replacement
Object Lock changes
KMS/encryption changes
IAM wildcard actions/resources
API authorizer changes
Lambda environment variables
EventBridge recovery schedule
workflow state GSI
CloudWatch log retention
```

Stop if Terraform wants to destroy shared or protected data stores unexpectedly.

---

## Required post-apply checks

After apply:

```bash
terraform output
```

Then verify:

```text
API endpoint exists
Cognito/JWT auth configured
DynamoDB tables exist
workflow state table has recovery_due_index
conversation table exists
transcript bucket exists if enabled
audit archive bucket exists if enabled
Recovery Daemon Lambda exists
EventBridge schedule enabled
CloudWatch log groups exist
```

---

## Smoke tests

Run smoke tests for:

```text
normal authenticated request
trusted tenant context creation
cross-tenant denial
customer_lookup for owned customer
billing_check read-only path
ticket_creation idempotency
account_credit pending approval
approval replay denial
conversation message persistence
workflow state persistence
recovery daemon invocation
```

---

## Common Terraform/AWS pitfalls

```text
wrong AWS profile
wrong region
Bedrock model unavailable in region
S3 bucket name already taken
Object Lock blocks destroy
DynamoDB table already exists
GSI replacement risk
Lambda package path missing
IAM permissions too weak
IAM permissions too broad
CloudWatch retention omitted
```

See also: [`aws-deployment-guide-for-junior-engineers.md`](aws-deployment-guide-for-junior-engineers.md)

---

## Destroy warning

For dev/lab only:

```bash
terraform destroy -var-file=environments/dev/terraform.tfvars
```

Before destroy, check:

```text
S3 Object Lock retention
non-empty transcript/audit buckets
DynamoDB data you need
correct account/region/environment
```

Do not use destroy as a production rollback strategy.


## Live red-team override flag

The v0.2.4 live red-team harness can test poisoned retrieved context and malicious tool-output channels through the real request router. This uses explicit test-only request fields and requires:

```hcl
enable_redteam_overrides = true
redteam_override_roles = ["redteam-operator"]
```

Use this only in dev/staging with test tenants and non-production data. Production should keep:

```hcl
enable_redteam_overrides = false
```

If the flag is disabled, the router returns `redteam_overrides_disabled` and the live red-team scorer treats that as a failed test, not as successful blocking.
