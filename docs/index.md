# Maci Documentation Index

This directory documents the Maci governed AI agent control-plane foundation.

The documentation is organized by reader intent.

---

## 1. Understand the problem

- [`business-painpoint.md`](business-painpoint.md) — why PoC agents break down near real business data and workflows.
- [`governed-ai-support-agent-workflow.md`](governed-ai-support-agent-workflow.md) — narrative use case from login to final response.
- [`industry-best-practices-2026.md`](industry-best-practices-2026.md) — supporting context only; not compliance evidence.

---

## 2. Understand the system

- [`architecture.md`](architecture.md) — complete technical architecture, including normal runtime and recovery runtime.
- [`conversation-history.md`](conversation-history.md) — user-facing conversation history and transcript storage.
- [`agent-conversation-logging-and-audit-guide.md`](agent-conversation-logging-and-audit-guide.md) — difference between transcript, audit, logs, and usage ledger.
- [`workflow-state-machine.md`](workflow-state-machine.md) — durable workflow states and resume classification.
- [`recovery-daemon-operating-model.md`](recovery-daemon-operating-model.md) — scheduled recovery daemon design.
- [`conversation-ownership-and-tool-recovery-wiring.md`](conversation-ownership-and-tool-recovery-wiring.md) — v0.1.7 review-fix notes for owner-checked conversation resume and real tool workflow transitions.
- [`api-waf-rate-limiting-and-pii-redaction.md`](api-waf-rate-limiting-and-pii-redaction.md) — v0.2.0 API abuse protection and transcript/audit redaction layer.
- [`prompt-injection-red-team-suite.md`](prompt-injection-red-team-suite.md) — v0.2.1 prompt-injection, poisoned RAG, tool-output injection and jailbreak red-team suite.

---

## 3. Deploy and operate

- [`aws-first-deploy-lab.md`](aws-first-deploy-lab.md) — first AWS dev deployment lab.
- [`aws-deployment-guide-for-junior-engineers.md`](aws-deployment-guide-for-junior-engineers.md) — beginner-friendly AWS deployment help and pitfalls.
- [`terraform-deployment.md`](terraform-deployment.md) — Terraform-first deployment model.
- [`aws-deployment.md`](aws-deployment.md) — legacy/SAM deployment notes.
- [`cicd-and-recovery-operating-model.md`](cicd-and-recovery-operating-model.md) — CI/CD, deploy gates, rollback and restart model.
- [`runbook.md`](runbook.md) — operational runbook for common incidents.
- [`recovery-playbooks.md`](recovery-playbooks.md) — specific recovery scenarios.

---

## 4. Security and readiness

- [`security-hardening.md`](security-hardening.md) — implemented security controls.
- [`threat-model.md`](threat-model.md) — threat model and mitigations.
- [`production-readiness.md`](production-readiness.md) — promotion gates before real production.
- [`limitations.md`](limitations.md) — honest boundaries and what still requires AWS validation.
- [`documentation-audit.md`](documentation-audit.md) — documentation/code consistency notes.

---

## 5. Code audit notes

- [`code-audit-v0.1.1.md`](code-audit-v0.1.1.md)
- [`code-audit-v0.1.2.md`](code-audit-v0.1.2.md)
- [`code-audit-v0.1.3.md`](code-audit-v0.1.3.md)
- [`code-audit-v0.1.4.md`](code-audit-v0.1.4.md)
- [`code-audit-v0.1.5.md`](code-audit-v0.1.5.md)
- [`code-audit-v0.1.6.md`](code-audit-v0.1.6.md)
- [`code-audit-v0.1.7.md`](code-audit-v0.1.7.md)
- [`code-audit-v0.2.0.md`](code-audit-v0.2.0.md)
- [`code-audit-v0.2.1.md`](code-audit-v0.2.1.md)

---

## Recommended reading order

For a new engineer:

```text
1. business-painpoint.md
2. governed-ai-support-agent-workflow.md
3. architecture.md
4. conversation-history.md
5. workflow-state-machine.md
6. recovery-daemon-operating-model.md
7. aws-deployment-guide-for-junior-engineers.md
8. runbook.md
9. production-readiness.md
10. limitations.md
```

For a reviewer/interviewer:

```text
1. README.md
2. architecture.md
3. security-hardening.md
4. threat-model.md
5. recovery-daemon-operating-model.md
6. conversation-ownership-and-tool-recovery-wiring.md
7. api-waf-rate-limiting-and-pii-redaction.md
8. prompt-injection-red-team-suite.md
9. code-audit-v0.2.1.md
10. limitations.md
```


- [Code Audit v0.2.2](code-audit-v0.2.2.md)

- [`docs/code-audit-v0.2.4.md`](code-audit-v0.2.4.md) — redaction metric preservation and live red-team integration fixes.

- [Code Audit v0.2.5](code-audit-v0.2.5.md) — CI gates and red-team override authorization.
