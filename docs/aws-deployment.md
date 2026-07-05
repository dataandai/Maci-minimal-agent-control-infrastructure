# AWS Deployment Notes

This document summarizes AWS deployment choices for Maci.

For the beginner step-by-step guide, use [`aws-first-deploy-lab.md`](aws-first-deploy-lab.md).  
For a junior-engineer guide with pitfalls, use [`aws-deployment-guide-for-junior-engineers.md`](aws-deployment-guide-for-junior-engineers.md).  
For Terraform details, use [`terraform-deployment.md`](terraform-deployment.md).

---

## Deployment source of truth

Use Terraform for the full Maci stack:

```text
infra/terraform
```

The SAM template is a lightweight compatibility/dev starter only.

---

## Required AWS services

A representative deployment uses:

```text
API Gateway
Cognito or enterprise OIDC/JWT authorizer
Lambda
DynamoDB
S3
CloudWatch Logs/Metrics
EventBridge
Step Functions optional workflow skeleton
Amazon Bedrock Runtime / Agent Runtime / Knowledge Bases as configured
KMS recommended for encryption
```

---

## Bedrock setup

Before real model calls:

```text
choose AWS region
confirm model availability
request model access
configure model IDs in tenant policy
grant Lambda role Bedrock permissions
configure guardrails/KBs/Agents if used
```

Start labs with real Bedrock disabled if possible.

---

## Required seed data

A useful dev deployment needs:

```text
tenant record/policy
agent registry record
resource ownership records
allowed tool policy
approval role/test user
demo customer ownership
demo budget limits
```

Without resource ownership records, tool calls may correctly fail.

---

## Recovery deployment notes

The recovery daemon requires:

```text
workflow state table
recovery_due_index GSI
RecoveryDaemonFunction Lambda
EventBridge schedule
IAM permissions to read/write workflow state
IAM permissions to write audit/conversation status
```

Test it with a stale workflow record before relying on it.

---

## Conversation deployment notes

Conversation history requires:

```text
conversation metadata/message table
optional transcript S3 bucket
KMS/encryption decisions
retention policy
tenant-scoped read API before exposing transcripts
```

Do not expose raw transcript storage directly to users.

---

## Production warning

A successful AWS deploy is not the same as production readiness.

Before production, complete:

```text
IAM least privilege review
Terraform plan review
load test
recovery/chaos test
prompt-injection red-team
privacy/retention review
runbook/on-call review
cost/budget review
```
