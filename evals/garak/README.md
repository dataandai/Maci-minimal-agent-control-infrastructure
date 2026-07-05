# Optional garak Red-Team Runner

This directory is a placeholder for external live-model red-team runs.

The local MACI test suite is deterministic and model-free. It must run in CI.
Use garak only against a deployed dev/staging endpoint or a selected Bedrock model
when you intentionally want live-model vulnerability scanning.

Example usage depends on the provider and target adapter you choose. Keep it out
of the default unit-test path because it may call paid model APIs and can be
non-deterministic.

Useful categories to run against an agent system:

```text
prompt injection
jailbreaks
data leakage
sensitive information disclosure
tool misuse / excessive agency
```

Do not run live red-team probes against production tenants without written
approval, explicit rate limits, test accounts, and monitoring.
