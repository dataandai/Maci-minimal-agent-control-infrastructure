# Code audit v0.1.3

This release addresses the two concrete code-level findings from the independent v0.1.2 review that could still be fixed without a live AWS account.

## Implemented in code

- **DynamoDB-backed audit hash chain**: `audit.py` no longer reads the previous audit hash only from process-local memory when a DynamoDB audit table is configured. It reads a per-tenant chain-head item and appends events with a conditional DynamoDB `TransactWriteItems` operation.
- **Concurrent Lambda safety for audit chaining**: competing audit writers now retry on chain-head conflicts rather than producing divergent per-container chains.
- **Audit sequence numbers**: audit events include `sequence_number` in addition to `previous_event_hash` and `event_hash`, so downstream verification can check both order and hash linkage.
- **Circuit-breaker any-category visibility**: `TenantCircuitBreaker.is_open(tenant_id)` in DynamoDB mode now queries the tenant partition to report whether any category is open, instead of returning a blind `False` to avoid scanning.

## Locally validated

```text
42 passed
python compileall OK
quickstart bash syntax OK
```

## Important remaining truth boundary

The DynamoDB transaction path is covered by a local fake DynamoDB table that verifies the intended write pattern and hash-chain behavior across distinct `AuditLogger` instances. A real AWS environment must still run:

```bash
terraform fmt -recursive
terraform validate
terraform plan -var-file=environments/dev/terraform.tfvars
terraform apply -var-file=environments/dev/terraform.tfvars
```

Then validate the same audit chain behavior against the real DynamoDB audit table under concurrent Lambda load.
