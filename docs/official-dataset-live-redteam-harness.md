# Official Dataset + Live Red-Team Harness

This document explains the official/public dataset and live endpoint red-team harness. v0.2.4 fixes the live integration path so schema errors are no longer counted as successful guardrail blocking.

The earlier red-team layer used deterministic local fixtures. That was useful for CI, but it was not enough to prove that the system can be tested with real benchmark-style datasets or against a deployed dev/staging API.

v0.2.2 adds two missing pieces:

```text
1. Dataset adapters for public/official red-team benchmark exports.
2. A live HTTP endpoint runner for dev/staging API testing.
```

The goal is not to pretend that a local string fixture is a full RAG or live-model red-team test. The goal is to make the evaluation path explicit and executable.

---

## 1. What Changed

New components:

```text
src/maci/redteam.py
  RedTeamDatasetLoader
  RedTeamDatasetManifest
  LiveEndpointRedTeamRunner

evals/redteam/dataset_manifest.example.json
  dataset manifest for local JSONL exports

evals/redteam/official_samples/*.jsonl
  tiny sample/export shapes for supported dataset types

scripts/run_redteam_against_endpoint.py
  sends normalized red-team cases to a real dev/staging API endpoint

scripts/export_hf_redteam_dataset.py
  optional helper for exporting allowed Hugging Face dataset subsets to JSONL

tests/red_team/test_official_dataset_and_live_redteam.py
  tests loader normalization and real HTTP request scoring
```

---

## 2. Supported Dataset Adapter Names

The loader supports these normalized dataset names:

```text
prompt_injections_benchmark
lakera_pint
promptinject
jailbreakbench
harmbench
garak_promptinject
promptfoo_redteam
generic_jsonl
```

Maci does not ship full third-party datasets. Teams should export only the rows they are allowed to store and evaluate, then register those JSONL files in a manifest.

This keeps unit tests deterministic and avoids licensing/safety ambiguity.

---

## 3. Offline Dataset-Backed CI Test

Run the offline red-team tests:

```bash
pytest -q tests/red_team/
```

This runs:

```text
local deterministic cases
public-dataset-style JSONL samples
poisoned RAG context cases
tool-output injection cases
benign false-positive controls
```

The offline test does not call a model and does not need AWS.

It proves that dataset cases pass through the local application boundary:

```text
RedTeamDatasetLoader
  ↓
normalized RedTeamCase
  ↓
RedTeamRunner
  ↓
GuardrailChecker
  ↓
expected allow/intervene decision
```

---

## 4. Dataset Manifest

Example:

```json
{
  "datasets": [
    {
      "dataset_name": "prompt_injections_benchmark",
      "path": "official_samples/prompt_injections_benchmark_sample.jsonl",
      "source_url": "https://huggingface.co/datasets/rogue-security/prompt-injections-benchmark"
    },
    {
      "dataset_name": "lakera_pint",
      "path": "official_samples/lakera_pint_sample.jsonl",
      "source_url": "https://github.com/lakeraai/pint-benchmark"
    },
    {
      "dataset_name": "jailbreakbench",
      "path": "official_samples/jailbreakbench_sample.jsonl",
      "source_url": "https://github.com/JailbreakBench/jailbreakbench"
    }
  ]
}
```

The manifest lives at:

```text
evals/redteam/dataset_manifest.example.json
```

For real use, create an environment-specific manifest, for example:

```text
evals/redteam/dataset_manifest.dev.json
```

Do not commit private customer data or sensitive attack payloads that your team is not allowed to store.

---

## 5. JSONL Normalization

The loader accepts common benchmark field names.

Text/payload fields:

```text
payload
text
prompt
attack
goal
behavior
instruction
input
query
content
```

Label fields:

```text
expected_action
label
classification
is_prompt_injection
is_jailbreak
category
```

IDs:

```text
case_id
id
idx
sample_id
behavior_id
```

Labels such as `jailbreak`, `attack`, `injection`, `malicious`, `unsafe`, `1`, or `true` map to:

```text
expected_action = intervene
```

Labels such as `benign`, `safe`, `clean`, `0`, or `false` map to:

```text
expected_action = allow
```

---

## 6. Live Endpoint Testing

Once a dev/staging API is deployed, run the same normalized cases against the real endpoint.

Example:

```bash
export MACI_REDTEAM_JWT="<test-tenant-jwt>"

python scripts/run_redteam_against_endpoint.py \
  --endpoint "https://<dev-api>/agent" \
  --manifest evals/redteam/dataset_manifest.example.json \
  --redteam-knowledge-base-id "kb-acme-support" \
  --redteam-tool-name "customer_lookup" \
  --output redteam-live-report.json
```

The live runner sends real HTTP requests.

It does not mock the API.

It scores each case by checking whether the endpoint blocked or allowed it as expected.

Blocking is detected only from explicit security-control outcomes, not from arbitrary HTTP status codes.

The runner counts these markers as blocked:

```text
guardrail_intervened
policy_denied
kill_switch_active
tenant_circuit_open
safe_stop
approval_required
tool_disabled
resource_not_allowed
```

Important: generic schema failures are **not** counted as passed blocking. For example, these are live-harness failures because they prove the case did not reach the intended guardrail path:

```text
invalid_request_schema
redteam_overrides_disabled
missing_trusted_identity
```

Use only:

```text
dev/staging environment
test tenant
test users
test knowledge base
test business backends
no production customer data
```

For Terraform dev/staging deployments, enable the test-only override plumbing explicitly:

```hcl
enable_redteam_overrides = true
redteam_override_roles = ["redteam-operator"]
```

The caller JWT must include one of the configured roles. Production must keep the override disabled:

```hcl
enable_redteam_overrides = false
```

---

## 7. RAG Poisoning: Current and Next Level

v0.2.2 supports RAG poisoning cases as a first-class channel:

```text
channel = retrieved_context
```

In offline CI, these are still simulated retrieved chunks.

In live endpoint testing, the runner sends them through explicit test-only request fields:

```text
redteam_context_override
redteam_tool_output_override
```

The real `AgentRequest` schema accepts these fields, but the request router only honors them when the deployed dev/staging Lambda has both gates enabled:

```text
ENABLE_REDTEAM_OVERRIDES=true
REDTEAM_OVERRIDE_ROLES=redteam-operator
```

The caller JWT must include one of the allowed red-team roles, for example `redteam-operator`. A normal support user must not be able to inject retrieved context or tool output directly into the live endpoint.

If the environment flag is absent, the router returns `redteam_overrides_disabled`. If the caller role is missing, it returns `redteam_role_required`. The live harness treats both as failed tests rather than as successful blocking. This prevents false-positive "100% blocked" reports caused by disabled test plumbing or an unauthorized caller.

For a true end-to-end RAG poisoning test, the next level is:

```text
1. ingest poisoned documents into a test-tenant KB
2. query the KB through the deployed retrieval path
3. confirm poisoned chunks are retrieved
4. confirm guardrails block them before prompt composition
5. confirm no unsafe tool call is produced
```

That belongs in a staging integration test, not a unit test.

---

## 8. How This Differs From the Old Fixture Tests

Old local fixture test:

```text
hardcoded string
  ↓
GuardrailChecker
  ↓
pass/fail
```

v0.2.2 dataset-backed offline test:

```text
public benchmark JSONL export
  ↓
manifest
  ↓
RedTeamDatasetLoader
  ↓
normalized RedTeamCase
  ↓
GuardrailChecker
  ↓
pass/fail
```

v0.2.2 live endpoint test:

```text
public benchmark JSONL export
  ↓
manifest
  ↓
RedTeamDatasetLoader
  ↓
LiveEndpointRedTeamRunner
  ↓
real HTTP API request
  ↓
API Gateway / WAF / Router / Guardrails / Policy
  ↓
pass/fail report
```

---

## 9. Safety Boundaries

Do not run live red-team datasets against production customer data.

Do not use admin users for live red-team tests.

Do not disable WAF/rate limits just to make tests faster.

Do not store hidden model chain-of-thought.

Do not treat one green benchmark as complete safety certification.

Do treat this as a repeatable regression gate.

---

## 10. Useful Public Evaluation Sources

The adapter layer is designed around public benchmark/tool formats such as:

- Lakera PINT Benchmark
- PromptInject
- JailbreakBench
- HarmBench
- garak promptinject probes
- promptfoo redteam-generated cases
- generic JSONL exports

Use each upstream dataset/tool according to its own license and safety guidance.


## v0.2.3 packaging guarantee

The red-team harness now includes a hard packaging gate. These files must exist in every release zip:

```text
evals/redteam/dataset_manifest.example.json
evals/redteam/README.md
evals/redteam/official_samples/prompt_injections_benchmark_sample.jsonl
evals/redteam/official_samples/lakera_pint_sample.jsonl
evals/redteam/official_samples/promptinject_sample.jsonl
evals/redteam/official_samples/jailbreakbench_sample.jsonl
evals/redteam/official_samples/harmbench_sample.jsonl
evals/redteam/official_samples/bipia_indirect_prompt_injection_sample.jsonl
evals/redteam/official_samples/rag_poisoned_docs_sample.jsonl
scripts/verify_redteam_assets.py
scripts/export_public_redteam_dataset.py
scripts/run_redteam_against_endpoint.py
```

Run:

```bash
python scripts/verify_redteam_assets.py
```

If any file is missing, the command exits non-zero. The unit test suite also contains an asset-packaging regression test so future releases cannot silently drop these files.

## Exporting real public datasets

The repository does not vendor full third-party datasets by default. Instead, it provides an exporter that converts permitted upstream rows into Maci's normalized JSONL format.

```bash
python scripts/export_public_redteam_dataset.py \
  --source hf \
  --hf-dataset JailbreakBench/JBB-Behaviors \
  --split train \
  --text-field behavior,prompt,goal \
  --dataset-name jailbreakbench \
  --category jailbreak \
  --output evals/redteam/exports/jailbreakbench_export.jsonl \
  --max-cases 100
```

For local JSONL/CSV exports:

```bash
python scripts/export_public_redteam_dataset.py \
  --source local \
  --input downloaded_dataset.jsonl \
  --text-field prompt,text,attack \
  --label-field label \
  --dataset-name prompt_injections_benchmark \
  --output evals/redteam/exports/prompt_injections_export.jsonl
```

Then add that file to a manifest and run either offline CI or live endpoint testing.


---

## v0.2.4 Integration Fixes

v0.2.4 closes a live-harness integration gap found during review.

Before v0.2.4, retrieved-context and tool-output live cases used fields that the real request schema rejected. The runner also counted any HTTP 400 as blocked, so those cases could appear to pass without exercising the guardrail.

The fixed path is now:

```text
public/sample JSONL case
  ↓
LiveEndpointRedTeamRunner
  ↓
real AgentRequest schema accepts test-only override field
  ↓
request_router verifies ENABLE_REDTEAM_OVERRIDES=true
  ↓
retrieved_context or tool_output guardrail executes
  ↓
explicit guardrail_intervened / allowed result is scored
```

Use this mode only in dev/staging with a test tenant and non-production data.
