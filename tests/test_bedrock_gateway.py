from maci.bedrock_gateway import BedrockGateway
from maci.schemas import BedrockAgentInvocationRequest, TenantContext


def test_invoke_agent_stub_uses_session_boundary():
    gateway = BedrockGateway(enable_real_bedrock=False)
    response = gateway.invoke_agent(
        BedrockAgentInvocationRequest(
            tenant_context=TenantContext(tenant_id="tenant-acme", user_id="u-1", request_id="req-1"),
            agent_id="AGENT12345",
            agent_alias_id="ALIAS12345",
            session_id="req-1",
            input_text="hello",
        )
    )
    assert response.agent_id == "AGENT12345"
    assert "sessionAttributes" in response.output_text
