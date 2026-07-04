from maci.policy_store import PolicyStore


def test_policy_store_falls_back_to_demo_policies_without_dynamodb(monkeypatch):
    monkeypatch.delenv("POLICY_TABLE_NAME", raising=False)
    policy = PolicyStore().get_policy("tenant-acme")
    assert policy.tenant_id == "tenant-acme"
    assert "customer_lookup" in policy.allowed_tools
