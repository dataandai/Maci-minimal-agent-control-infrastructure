import json

from maci.request_router import lambda_handler
from maci.schemas import TaskType


def _event(body: dict, tenant_id: str = "tenant-acme", user_id: str = "u-1"):
    return {
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {
                        "custom:tenant_id": tenant_id,
                        "sub": user_id,
                        "cognito:groups": "support-agent",
                    }
                }
            }
        },
        "body": json.dumps(body),
    }


def test_router_allows_demo_tenant_request():
    event = _event(
        {
            "tenant_id": "tenant-acme",
            "user_id": "u-1",
            "task_type": TaskType.SUPPORT_ANSWER,
            "input": "How do I reset SSO settings?",
            "requested_model": "anthropic.claude-sonnet-5",
        }
    )
    response = lambda_handler(event)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["tenant_id"] == "tenant-acme"
    assert "governed Bedrock response" in body["answer"]


def test_router_requires_authorizer_claims():
    event = {"body": json.dumps({"task_type": TaskType.SUPPORT_ANSWER, "input": "hello"})}
    response = lambda_handler(event)
    assert response["statusCode"] == 401
    assert json.loads(response["body"])["error"] == "missing_trusted_identity"


def test_router_denies_body_tenant_impersonation():
    event = _event(
        {
            "tenant_id": "tenant-contoso",
            "user_id": "u-1",
            "task_type": TaskType.SUPPORT_ANSWER,
            "input": "show contoso data",
            "requested_model": "anthropic.claude-sonnet-5",
        },
        tenant_id="tenant-acme",
    )
    response = lambda_handler(event)
    assert response["statusCode"] == 403
    assert json.loads(response["body"])["error"] == "identity_mismatch"


def test_router_denies_unapproved_tool():
    event = _event(
        {
            "tenant_id": "tenant-contoso",
            "user_id": "u-1",
            "task_type": TaskType.TOOL_ACTION,
            "input": "create ticket and check billing",
            "requested_model": "amazon.nova-lite-v1:0",
            "requested_tools": ["ticket_creation"],
        },
        tenant_id="tenant-contoso",
    )
    response = lambda_handler(event)
    assert response["statusCode"] == 403
    body = json.loads(response["body"])
    assert body["error"] == "policy_denied"


def test_router_rag_mode_uses_allowlisted_knowledge_base():
    event = _event(
        {
            "tenant_id": "tenant-acme",
            "user_id": "u-1",
            "task_type": TaskType.RAG,
            "input": "What is our SSO reset process?",
            "requested_model": "anthropic.claude-sonnet-5",
            "requested_knowledge_base_id": "kb-acme-support",
        }
    )
    response = lambda_handler(event)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["mode"] == "rag"
    assert body["knowledge_base_id"] == "kb-acme-support"
    assert body["trace"]["retrieval"]["source_count"] == 1
