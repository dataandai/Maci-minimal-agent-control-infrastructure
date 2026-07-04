# AWS Deployment Guide for Junior Engineers

This guide helps junior engineers deploy the Maci-style governed AI agent control-plane to AWS.

It is written as a practical wiki page, not as a marketing document. The goal is to explain what you are deploying, why each step matters, what can go wrong, and how to debug the most common issues.

> Important: this guide is for a development or lab deployment first. Do not treat the first successful `terraform apply` as production readiness.

---

## 1. What You Are Deploying

You are not deploying only a chatbot.

You are deploying an AWS-native control-plane around an AI agent workflow.

At a high level, the system contains:

```text
Client / Support Console
        ↓
API Gateway
        ↓
Request Router Lambda
        ↓
Agent Workflow / Step Functions
        ↓
Amazon Bedrock / LLM
        ↓
Tool Lambdas
        ↓
DynamoDB / S3 / CloudWatch / Business Backends
```

The purpose of the system is to let an AI agent help with support or billing workflows without giving the model unrestricted access to customer data or business actions.

The LLM can reason and request tool calls.

The system decides whether those tool calls are allowed.

---

## 2. Example Business Flow

A support user receives this customer request:

```text
We were charged incorrectly this month. Please check billing and apply a credit if needed.
```

In the deployed system, this becomes a controlled workflow:

```text
1. User logs in.
2. Identity is verified.
3. Tenant context is derived from trusted identity.
4. Request enters the API layer.
5. Router checks tenant, policy, budget, kill switch, and circuit breaker.
6. Input guardrails run.
7. The LLM plans the next step.
8. Tool calls are requested.
9. Tool handlers enforce authorization and resource ownership.
10. High-risk account credit creates a pending approval.
11. A human reviewer approves or rejects the exact operation.
12. Final response is validated.
13. Audit, usage, and trace events are written.
```

The important point:

> The LLM proposes actions. The system enforces whether those actions are allowed.

---

## 3. Before You Start

You should have basic familiarity with:

- AWS accounts;
- IAM roles and policies;
- AWS CLI;
- Terraform;
- Python virtual environments;
- Lambda;
- DynamoDB;
- S3;
- CloudWatch Logs;
- API Gateway;
- Amazon Bedrock basics.

You do not need to be an expert, but you should understand that AWS deployment changes real cloud resources and can generate real cost.

---

## 4. Local Prerequisites

Install these tools locally:

```text
Python 3.11+
pip
git
Terraform CLI
AWS CLI v2
```

Check them:

```bash
python --version
pip --version
git --version
terraform version
aws --version
```

If one of these commands fails, fix your local environment before touching AWS.

---

## 5. Clone the Repository

Clone the repository:

```bash
git clone <repo-url>
cd <repo-directory>
```

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the project with development and AWS dependencies:

```bash
pip install -e '.[dev,aws]'
```

Why `dev,aws`?

Some local tests may import AWS SDK packages such as `boto3`. If you install only development dependencies and AWS dependencies are separate, test collection may fail before any actual test runs.

---

## 6. Run Local Validation First

Before deploying anything to AWS, run local checks.

```bash
pytest
```

If the repository has shell scripts:

```bash
bash -n scripts/*.sh
```

If the repository has Python modules:

```bash
python -m compileall src tests
```

Do not skip this step.

If local tests fail, AWS deployment will not make the system better. It will only make debugging slower and more expensive.

---

## 7. Configure AWS Authentication

Use temporary credentials if possible.

Recommended approach for many teams:

```bash
aws configure sso
aws sso login --profile <profile-name>
```

Then confirm your identity:

```bash
aws sts get-caller-identity --profile <profile-name>
```

You should see the AWS account ID and the assumed role.

Common mistake:

```text
You think you are deploying to a sandbox account, but your AWS CLI profile points to another account.
```

Always check:

```bash
aws sts get-caller-identity
```

before running Terraform.

---

## 8. Choose the AWS Region

Pick one AWS Region for the lab deployment.

Example:

```text
us-east-1
eu-west-1
```

The region matters because:

- not every Bedrock model is available in every region;
- some service quotas are region-specific;
- Terraform state and deployed resources are region-specific;
- CloudWatch logs and DynamoDB tables are region-specific;
- model access must be available in the region you use.

Set the region consistently:

```bash
export AWS_REGION=us-east-1
export AWS_PROFILE=<profile-name>
```

On Windows PowerShell:

```powershell
$env:AWS_REGION="us-east-1"
$env:AWS_PROFILE="<profile-name>"
```

---

## 9. Request Amazon Bedrock Model Access

Before the agent can call a foundation model through Amazon Bedrock, the AWS account must have access to the selected model in the selected region.

If model access is missing, the infrastructure may deploy successfully, but runtime calls can fail with errors such as:

```text
AccessDeniedException
Model access is not enabled
The provided model identifier is invalid
```

Before testing the agent, verify:

```text
1. The model is available in your selected region.
2. Your AWS account has access to that model.
3. The Lambda execution role has permission to call the required Bedrock runtime API.
4. The model ID in configuration matches the actual Bedrock model ID.
```

Do not debug agent logic before confirming Bedrock model access.

---

## 10. Understand the Terraform Layout

A typical deployment may contain modules such as:

```text
terraform/
  main.tf
  variables.tf
  outputs.tf
  modules/
    api/
    auth/
    dynamodb/
    lambda_function/
    audit_archive/
    observability/
    stepfunctions/
```

The exact module names can differ, but the pattern is usually similar:

- API module creates API Gateway routes and authorizers.
- Auth module creates Cognito or JWT authorizer resources.
- DynamoDB module creates tables for policies, audit metadata, usage, approvals, circuit breakers, and ownership.
- Lambda module packages and deploys handlers.
- Audit archive module creates S3 storage for audit events.
- Observability module creates CloudWatch logs, metrics, alarms, or dashboards.
- Step Functions module creates workflow orchestration.

---

## 11. Create a Terraform Variables File

Create an environment-specific variables file.

Example:

```bash
cp terraform/example.tfvars terraform/dev.tfvars
```

Example values:

```hcl
environment = "dev"
project_name = "maci"
aws_region = "us-east-1"

bedrock_model_id = "your-selected-model-id"

enable_object_lock = true
enable_dynamodb_pitr = true

log_retention_days = 14
```

Never commit secrets into `.tfvars`.

If a value is secret, use AWS Secrets Manager, SSM Parameter Store, or your team’s approved secret-management approach.

---

## 12. Terraform Init

Go to the Terraform directory:

```bash
cd terraform
```

Initialize Terraform:

```bash
terraform init
```

This downloads providers and prepares the working directory.

If `terraform init` fails, common causes include:

- no internet access;
- provider registry blocked;
- invalid provider version constraint;
- missing backend configuration;
- wrong AWS credentials for remote state;
- existing backend state mismatch.

Do not run `apply` until `init` succeeds cleanly.

---

## 13. Terraform Format and Validate

Run formatting:

```bash
terraform fmt -recursive
```

Check formatting in CI mode:

```bash
terraform fmt -recursive -check
```

Run validation:

```bash
terraform validate
```

Important limitation:

`terraform validate` checks Terraform configuration structure. It does not prove that AWS will accept every resource at apply time.

A configuration can validate successfully and still fail during `plan` or `apply` because of AWS permissions, service quotas, unavailable regions, naming conflicts, or API constraints.

---

## 14. Terraform Plan

Run a plan:

```bash
terraform plan -var-file="dev.tfvars" -out=tfplan
```

Read the plan before applying.

Look for:

```text
Resources to add
Resources to change
Resources to destroy
IAM policies
S3 buckets
DynamoDB tables
Lambda roles
API Gateway routes
CloudWatch log groups
```

Do not apply a plan you do not understand.

For junior engineers, the goal is not to memorize every AWS resource. The goal is to notice obviously dangerous changes.

Red flags:

```text
Terraform wants to destroy shared resources.
Terraform wants to create resources in the wrong account.
Terraform wants to create resources in the wrong region.
Terraform wants to attach broad wildcard IAM permissions.
Terraform wants to replace an S3 bucket or DynamoDB table unexpectedly.
```

If you see these, stop and ask for review.

---

## 15. Terraform Apply

Apply only after the plan has been reviewed:

```bash
terraform apply tfplan
```

During apply, AWS may reject resources even if the plan looked fine.

Common causes:

- missing IAM permissions;
- service quota limits;
- region does not support a selected service or model;
- S3 bucket name already exists globally;
- Lambda package path is wrong;
- IAM role trust policy is invalid;
- API Gateway authorizer configuration is incomplete;
- DynamoDB table already exists;
- Object Lock configuration is incompatible with the target bucket;
- CloudWatch log group already exists with different retention settings.

Do not panic if the first apply fails.

Read the first error carefully. Fix that first. Do not randomly change five things at once.

---

## 16. After Apply: Capture Outputs

After successful apply, print outputs:

```bash
terraform output
```

Important outputs may include:

```text
api_base_url
cognito_user_pool_id
cognito_client_id
lambda_function_names
dynamodb_table_names
audit_bucket_name
cloudwatch_log_group_names
step_function_arn
```

Save these for smoke testing.

---

## 17. Seed Development Data

A lab deployment usually needs seed data.

Examples:

```text
tenant-acme
support-billing-agent
allowed tools
sample customer ownership record
sample policy records
sample approval roles
budget limits
```

If the repository has a seed script, run it after infrastructure creation.

Example:

```bash
python scripts/seed_demo_data.py --env dev
```

or:

```bash
make seed-dev
```

If there is no seed script, manually insert only the minimal required records.

Do not skip ownership records. Without them, tool calls may fail correctly because the system cannot prove that a customer belongs to a tenant.

---

## 18. Create a Test User

Create or configure a test support user.

The test user should represent a real role boundary:

```text
user_id   = anna.support.17
tenant_id = tenant-acme
roles     = support_agent
```

If testing human approval, create a second user:

```text
user_id   = bela.risk.04
tenant_id = tenant-acme
roles     = risk_approver
```

Do not test everything as an admin user.

If everything is tested as admin, you will not notice broken authorization boundaries.

---

## 19. Smoke Test: Normal Support Flow

Run a basic request:

```text
Check billing for customer cust-123. If there was an overcharge, create a ticket and request account credit.
```

Expected flow:

```text
1. Request accepted.
2. Tenant context created from trusted identity.
3. Input guardrail passes.
4. Agent requests customer lookup.
5. Customer ownership check passes.
6. Billing check runs.
7. Ticket is created.
8. Account credit is not executed immediately.
9. Pending approval is created.
10. Final response says approval is pending.
```

Expected result before approval:

```text
Customer found.
Billing issue detected.
Ticket created.
Account credit request is pending approval.
Credit not yet applied.
```

If the system says the credit was applied before approval, stop. That is a serious bug.

---

## 20. Smoke Test: Human Approval

Log in as the risk approver.

Approve the pending account credit.

Then continue or retry the credit execution with the approval ID.

Expected checks:

```text
approval exists
approval is approved
same tenant
same customer
same amount
same action
same payload hash
```

Expected result:

```text
Account credit applied.
Audit event written.
Usage event written.
Trace updated.
```

---

## 21. Smoke Test: Cross-Tenant Denial

Test that tenant isolation works.

Use a customer ID that belongs to another tenant:

```text
authenticated tenant = tenant-acme
requested customer   = contoso-001
```

Expected result:

```text
403 resource_not_allowed
```

The request should fail even if the customer ID has a valid format.

This proves that schema validation is not the only protection. Resource ownership must also be enforced.

---

## 22. Smoke Test: Model-Injected Tenant ID

Test that the model cannot inject tenant identity through tool arguments.

Try an input that causes a tool payload like:

```json
{
  "customer_id": "cust-123",
  "tenant_id": "tenant-contoso"
}
```

Expected result:

```text
invalid_tool_input
extra field forbidden
```

The trusted tenant context must still come from authenticated identity, not from model output.

---

## 23. Smoke Test: Approval Replay

Test approval replay protection.

Create approval for:

```text
customer = cust-123
amount   = 500 USD
```

Then try to reuse the same approval for:

```text
customer = cust-123
amount   = 5000 USD
```

Expected result:

```text
approval_not_valid
```

The approval must be bound to the exact payload.

---

## 24. Smoke Test: Kill Switch

Enable a tool-level kill switch for account credit.

Then request account credit again.

Expected result:

```text
tool_disabled
workflow stopped or degraded
audit event written
```

Disable the kill switch after the test.

---

## 25. Smoke Test: Circuit Breaker

Trigger repeated validation failures in a controlled test environment.

For example, send repeated invalid tool inputs.

Expected result after threshold:

```text
circuit_breaker_open
workflow stopped
audit event written
```

The circuit breaker should be scoped carefully. A problem in one tenant should not automatically break all tenants unless it is a global failure mode.

---

## 26. Check CloudWatch Logs

After smoke tests, check logs.

Look for:

```text
Request Router Lambda logs
Tool Lambda logs
Approval workflow logs
Step Functions execution logs
API Gateway access logs
Bedrock invocation errors
```

Useful things to search for:

```text
ERROR
AccessDenied
ValidationError
ResourceNotAllowed
ApprovalRequired
CircuitBreakerOpen
GuardrailIntervened
```

Common mistake:

```text
The API returns 500, but the real error is hidden in the Lambda logs.
```

Always check logs before changing infrastructure.

---

## 27. Check DynamoDB Tables

Verify that records were created.

Tables may include:

```text
tenants
agent_registry
tool_policies
resource_ownership
approvals
usage_ledger
audit_events
circuit_breakers
```

Check that:

- tenant records exist;
- agent registry records exist;
- customer ownership records exist;
- approval records are created;
- usage records are written;
- circuit breaker state is visible;
- audit metadata is written.

If a tool call fails with authorization or ownership errors, missing seed records are often the cause.

---

## 28. Check S3 Audit Archive

If audit archive is enabled, verify that audit objects are written to S3.

Important checks:

```text
bucket exists
versioning enabled
object lock configured if required
objects are written
retention behavior works as expected
Lambda role can write audit objects
operators cannot casually delete protected audit objects
```

Be careful with Object Lock in lab environments.

Object Lock and retention settings can prevent deletion. This can affect `terraform destroy`.

---

## 29. Common Deployment Pitfalls

### 29.1 Wrong AWS Account

Symptom:

```text
Resources appear in the wrong account.
```

Check:

```bash
aws sts get-caller-identity
```

Fix:

```bash
export AWS_PROFILE=<correct-profile>
aws sso login --profile <correct-profile>
```

---

### 29.2 Wrong Region

Symptom:

```text
Bedrock model not found
DynamoDB table not found
CloudWatch logs empty
API URL points to unexpected region
```

Check:

```bash
echo $AWS_REGION
aws configure get region
```

Fix:

```bash
export AWS_REGION=<correct-region>
```

---

### 29.3 Bedrock Model Access Missing

Symptom:

```text
AccessDeniedException
Model access is not enabled
Model identifier invalid
```

Fix:

```text
Request model access in Amazon Bedrock.
Confirm the selected model is available in the selected region.
Confirm Lambda IAM permissions for Bedrock Runtime.
Confirm the configured model ID is correct.
```

---

### 29.4 Terraform Validate Passes but Apply Fails

Symptom:

```text
terraform validate succeeded
terraform apply failed
```

Why:

```text
validate checks Terraform configuration, not all live AWS API constraints.
```

Fix:

```text
Read the first AWS error.
Check permissions, quotas, naming, region support, and existing resources.
```

---

### 29.5 S3 Bucket Name Conflict

Symptom:

```text
BucketAlreadyExists
```

Why:

```text
S3 bucket names are globally unique.
```

Fix:

```text
Add account ID, region, or random suffix to bucket names.
```

---

### 29.6 Object Lock Blocks Destroy

Symptom:

```text
terraform destroy fails
S3 bucket cannot be emptied
objects cannot be deleted
```

Why:

```text
Object Lock retention can prevent object deletion.
```

Fix:

```text
Use short retention in lab environments.
Understand retention mode before enabling it.
Never enable long retention casually in a sandbox.
```

---

### 29.7 Missing Lambda Environment Variables

Symptom:

```text
Lambda starts but fails at runtime.
KeyError or missing configuration value.
```

Fix:

```text
Check Terraform variables.
Check Lambda environment variables.
Check whether secrets should come from Secrets Manager or SSM instead.
```

Do not store database passwords, API tokens, or long-lived secrets directly in Lambda environment variables.

---

### 29.8 Lambda IAM Role Too Weak

Symptom:

```text
AccessDeniedException
```

Examples:

```text
Lambda cannot read DynamoDB.
Lambda cannot write CloudWatch logs.
Lambda cannot invoke Bedrock.
Lambda cannot write to S3 audit bucket.
```

Fix:

```text
Add the minimum required permission.
Avoid broad wildcard policies unless this is explicitly a short-lived lab exception.
```

---

### 29.9 Lambda IAM Role Too Broad

Symptom:

```text
Everything works, but the role has dangerous permissions.
```

Examples:

```text
Action = "*"
Resource = "*"
```

Fix:

```text
Reduce permissions after confirming required access.
Use least privilege.
Scope permissions to specific tables, buckets, log groups, and model actions where possible.
```

---

### 29.10 Missing Resource Ownership Records

Symptom:

```text
customer_lookup denied
billing_check denied
resource_not_allowed
```

Why:

```text
The customer exists, but the system cannot prove it belongs to the authenticated tenant.
```

Fix:

```text
Seed resource ownership records.
Do not bypass this check.
```

---

### 29.11 Testing Only With Admin Users

Symptom:

```text
Everything works in testing, but real support users fail.
```

Why:

```text
Admin users bypass normal role boundaries.
```

Fix:

```text
Test with realistic roles:
support_agent
risk_approver
tenant_admin
read_only_user
```

---

### 29.12 Approval Flow Executes Too Early

Symptom:

```text
Account credit is applied before approval.
```

This is a critical bug.

Expected behavior:

```text
High-risk action creates pending approval.
No credit is applied until approved.
Approval must match exact payload.
```

Fix:

```text
Stop testing.
Review account_credit handler.
Review approval status checks.
Review payload hash verification.
Add a failing regression test.
```

---

### 29.13 Audit Events Missing on Deny

Symptom:

```text
Allowed actions are audited, but denied actions are not.
```

Why this is bad:

```text
Security-relevant denials are often more important than successful calls.
```

Fix:

```text
Audit both allow and deny paths.
Include denial reason.
Include tenant, user, agent, tool, and resource context.
```

---

### 29.14 Circuit Breaker Not Visible Across Lambdas

Symptom:

```text
One Lambda opens a circuit breaker, but another Lambda does not see it.
```

Why:

```text
Circuit breaker state stored only in memory is not shared across Lambda execution environments.
```

Fix:

```text
Use shared backing storage such as DynamoDB for tenant-scoped circuit breaker state.
```

---

### 29.15 Local Tests Require AWS Extras

Symptom:

```text
ModuleNotFoundError: No module named 'boto3'
```

Fix:

```bash
pip install -e '.[dev,aws]'
```

---

## 30. Safe Rollback Strategy

Before changing infrastructure, always know how to roll back.

Basic options:

```text
1. Revert the application code and redeploy Lambda.
2. Disable an agent using agent registry status.
3. Enable a tool-level kill switch.
4. Enable a tenant-level kill switch.
5. Revert Terraform changes.
6. Restore DynamoDB data from backup if enabled.
7. Preserve audit logs.
```

Do not rely only on `terraform destroy`.

Destroying infrastructure is not the same as safely rolling back a production incident.

---

## 31. Terraform Destroy in Lab Environments

For a lab environment, you may eventually destroy resources:

```bash
terraform destroy -var-file="dev.tfvars"
```

Before running destroy, check:

```text
Is this the correct AWS account?
Is this the correct region?
Is this a lab environment?
Are there protected S3 objects?
Are there DynamoDB tables with data you need?
Are there log groups you want to keep?
```

Object Lock, retention policies, and non-empty buckets can block destroy.

That is a feature, not always a bug.

---

## 32. Minimum Definition of a Successful Lab Deployment

A deployment is not successful just because Terraform completed.

A useful lab deployment should prove:

```text
Terraform apply succeeded.
API endpoint is reachable.
Test user can authenticate.
Trusted tenant context is created.
Normal support flow runs.
Customer lookup enforces tenant ownership.
Billing check runs for allowed resources.
Ticket creation works.
Account credit creates pending approval.
Credit cannot execute before approval.
Human approval works.
Approval replay is blocked.
Audit events are written.
Usage events are written.
Logs and traces are visible.
Kill switch works.
Circuit breaker works.
Terraform destroy or cleanup strategy is understood.
```

If these are not verified, the deployment is incomplete.

---

## 33. What Not To Do

Do not:

```text
Use root AWS credentials.
Deploy first and read the plan later.
Test only as admin.
Hardcode tenant_id in requests.
Trust tenant_id from the model.
Skip resource ownership checks.
Let high-risk tools execute directly.
Store secrets in plain environment variables.
Ignore AccessDenied errors by adding wildcard IAM everywhere.
Enable long Object Lock retention in a throwaway lab.
Assume Terraform validate means AWS deployment will succeed.
Assume one green demo means production readiness.
```

---

## 34. Junior Engineer Mental Model

Think of the system as three layers.

### Layer 1: Cloud entry and identity

```text
Who is calling?
Which tenant are they really acting for?
Which role do they have?
```

### Layer 2: Agent reasoning

```text
What does the user want?
What should the next step be?
Which tool does the agent want to call?
```

### Layer 3: Deterministic enforcement

```text
Is this tool allowed?
Is this resource owned by the tenant?
Is this operation high-risk?
Is approval required?
Should this be audited?
Should the circuit breaker stop it?
```

The LLM belongs mostly to Layer 2.

Security belongs mostly to Layer 1 and Layer 3.

Do not move security decisions into the prompt.

---

## 35. Final Summary

This deployment is not about making an LLM call tools.

That is the easy part.

The real purpose is to deploy the infrastructure that decides whether an LLM-requested action is safe, allowed, auditable, and reversible.

A PoC agent asks:

```text
Can the model call the tool?
```

A production-style agent system asks:

```text
Can this authenticated user, in this tenant, through this agent,
perform this action, on this resource, right now,
under policy, with audit, cost tracking, and rollback controls?
```

That is what this AWS deployment is meant to demonstrate.

---

## 36. Official References to Check

These references are useful when debugging or hardening the deployment:

- AWS IAM best practices and least privilege:
  - https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html
  - https://docs.aws.amazon.com/IAM/latest/UserGuide/getting-started-reduce-permissions.html

- AWS CLI SSO configuration:
  - https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html

- Amazon Bedrock model access:
  - https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html

- Amazon Bedrock supported models:
  - https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html

- Terraform CLI commands:
  - https://developer.hashicorp.com/terraform/cli/commands
  - https://developer.hashicorp.com/terraform/cli/commands/validate
  - https://developer.hashicorp.com/terraform/cli/commands/plan
  - https://developer.hashicorp.com/terraform/cli/commands/apply

- S3 Object Lock:
  - https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html
  - https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock-configure.html

- DynamoDB point-in-time recovery:
  - https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Point-in-time-recovery.html

- Lambda environment variables and secrets:
  - https://docs.aws.amazon.com/lambda/latest/dg/configuration-envvars.html
