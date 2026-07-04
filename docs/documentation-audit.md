# Documentation audit

This audit checks whether the documentation reflects the current Maci code and infrastructure state.

## Summary

The repository documentation is broadly aligned with the security-hardening direction, but Maci introduced a split between two deployment paths:

- **Terraform**: primary, full Maci deployment path.
- **SAM**: lightweight compatibility starter, not full Maci parity.

The most important documentation fix is to avoid presenting the SAM template as equivalent to the Terraform deployment.

## Verified locally

- Python test suite passes: `44 passed`.
- Python files compile with `compileall`.
- Linux quickstart shell scripts pass `bash -n` syntax checks.
- Markdown relative links resolve.
- Terraform files exist in a multi-environment structure.

Terraform itself was not available in this sandbox, so `terraform fmt`, `terraform validate` and `terraform plan` must run in the target environment or CI.

## Documentation/code alignment matrix

| Area | Documentation status | Code/infra status | Action |
|---|---|---|---|
| Primary deployment path | Updated to Terraform-first | Terraform includes Maci modules/resources | Keep Terraform as source of truth |
| SAM deployment | Reframed as lightweight starter | SAM lacks agent registry, approval queue, S3 archive and new tools | Do not market SAM as full Maci |
| Tenant identity | Aligned | JWT/sessionAttributes code implemented and tested | OK |
| Tool identity isolation | Aligned | model-generated tenant/user fields absent from tool schemas | OK |
| Per-operation authorization | Aligned | `authorization.py` used by tool handlers | OK |
| Agent identity registry | Aligned for Terraform | Terraform creates table; SAM does not | Terraform-only for the full Maci stack |
| Human approval | Aligned for Terraform/code | approval store/API/tool flow implemented | Requires AWS smoke test |
| S3 audit archive | Aligned for Terraform/code | audit archive module exists | Requires Object Lock validation in AWS |
| Observability | Partially aligned | CloudWatch + OTel-shaped JSON exists | Full OTel exporter not included |
| Examples | Updated to avoid identity in body by default | smoke test no longer sends tenant_id unless requested | OK |

## Remaining documentation risks

1. The Maci architecture diagram is stronger than the current AWS-proven deployment state. Keep the wording as “production-oriented foundation” until Terraform is applied and smoke-tested in AWS.
2. `industry-best-practices-2026.md` contains external source links gathered during research. Treat it as supporting context, not as generated compliance evidence.
3. `infra/iam-policies/least-privilege-notes.md` should be revisited after the first real Terraform plan because IAM tightening depends on concrete Bedrock Agent and Knowledge Base ARNs.
4. Production approval wording should remain conditional until IdP-side MFA/hardware-backed approval is configured.

## Gate before public release

Before publishing the repository publicly:

```bash
python -m pytest
python -m compileall -q src scripts tests
bash -n quickstart/linux/*.sh
cd infra/terraform
terraform fmt -recursive
terraform init -backend=false
terraform validate
terraform plan -var-file=environments/dev/terraform.tfvars
```

Then deploy in a dev AWS account and run the quickstart smoke test end to end.
