import json

from maci.agent_tools.customer_lookup.handler import lambda_handler as customer_lookup
from maci.agent_tools.ticket_creation.handler import lambda_handler as ticket_creation


def _bedrock_event(parameters: dict, tenant_id: str = "tenant-acme", user_id: str = "u-1"):
    return {
        "sessionAttributes": {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "request_id": "req-test",
        },
        "parameters": [{"name": key, "type": "string", "value": value} for key, value in parameters.items()],
    }


def test_customer_lookup_uses_session_tenant_not_model_parameters():
    event = _bedrock_event({"customer_id": "cust-999", "reason": "routine support check"}, tenant_id="tenant-contoso")
    response = customer_lookup(event)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["tenant_id"] == "tenant-contoso"
    assert body["customer_id"] == "cust-999"


def test_customer_lookup_rejects_model_generated_tenant_id():
    event = _bedrock_event(
        {
            "tenant_id": "tenant-other",
            "customer_id": "cust-999",
            "reason": "routine support check",
        },
        tenant_id="tenant-contoso",
    )
    response = customer_lookup(event)
    assert response["statusCode"] == 400
    assert json.loads(response["body"])["error"] == "invalid_tool_input"


def test_customer_lookup_rejects_unknown_session_tenant():
    event = _bedrock_event({"customer_id": "cust-999", "reason": "routine support check"}, tenant_id="tenant-never-provisioned")
    response = customer_lookup(event)
    assert response["statusCode"] == 403
    assert json.loads(response["body"])["error"] == "tool_not_allowed"


def test_ticket_creation_rejects_tool_not_allowlisted_for_tenant():
    event = _bedrock_event(
        {
            "customer_id": "cust-999",
            "title": "Reset SSO",
            "description": "Customer cannot access SSO after IdP certificate rotation.",
            "priority": "high",
        },
        tenant_id="tenant-contoso",
    )
    response = ticket_creation(event)
    assert response["statusCode"] == 403
    assert json.loads(response["body"])["error"] == "tool_not_allowed"


def test_customer_lookup_returns_bedrock_function_response_shape():
    event = _bedrock_event({"customer_id": "cust-999", "reason": "routine support check"})
    event.update({"messageVersion": "1.0", "actionGroup": "customer_lookup", "function": "customer_lookup"})
    response = customer_lookup(event)
    assert response["messageVersion"] == "1.0"
    assert response["response"]["function"] == "customer_lookup"
    assert "functionResponse" in response["response"]
    assert response["sessionAttributes"]["tenant_id"] == "tenant-acme"


def test_ticket_creation_is_idempotent_for_same_request():
    event = _bedrock_event(
        {
            "customer_id": "cust-123",
            "title": "Cannot log in",
            "description": "Customer cannot log in after identity provider change.",
            "priority": "high",
        }
    )
    first = ticket_creation(event)
    second = ticket_creation(event)
    assert first["statusCode"] == 200
    assert second["statusCode"] == 200
    first_body = json.loads(first["body"])
    second_body = json.loads(second["body"])
    assert first_body["ticket_id"] == second_body["ticket_id"]
    assert first_body["created"] is True
    assert second_body["created"] is False
