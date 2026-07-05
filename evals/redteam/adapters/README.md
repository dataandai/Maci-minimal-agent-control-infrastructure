# Red-Team Dataset Adapters

Maci does not download public red-team datasets during unit tests. Instead, teams export the rows they are allowed to use into JSONL and register them in `evals/redteam/dataset_manifest.example.json` or an environment-specific manifest.

Supported adapter names:

- `prompt_injections_benchmark`
- `lakera_pint`
- `promptinject`
- `jailbreakbench`
- `harmbench`
- `garak_promptinject`
- `promptfoo_redteam`
- `generic_jsonl`

The loader normalizes common fields such as `text`, `prompt`, `attack`, `behavior`, `label`, `category`, `expected_action`, `channel`, and `payload` into `maci.redteam.RedTeamCase`.

For live testing, use `scripts/run_redteam_against_endpoint.py` with a dev/staging API endpoint and a test-tenant JWT. Do not run live red-team datasets against production customer data.
