# Least Privilege Notes

The SAM template intentionally uses broad Bedrock resources because model, guardrail, and knowledge-base ARNs vary by account and region.

For production:

- scope Bedrock permissions to approved foundation model ARNs where possible;
- scope Knowledge Base access to tenant-specific KB ARNs;
- prevent wildcard tool execution;
- separate policy-read and audit-write roles;
- deny direct public invocation of tool Lambdas except via the router/agent boundary;
- enable CloudWatch log retention and encryption;
- use KMS customer-managed keys where required.
