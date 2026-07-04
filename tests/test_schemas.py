import pytest
from pydantic import ValidationError

from maci.schemas import AgentRequest, CustomerLookupInput, TaskType


def test_agent_request_forbids_unknown_fields():
    with pytest.raises(ValidationError):
        AgentRequest.model_validate(
            {
                "tenant_id": "tenant-acme",
                "user_id": "u-1",
                "task_type": TaskType.SUPPORT_ANSWER,
                "input": "hello",
                "unexpected": "must fail",
            }
        )


def test_tool_input_forbids_hallucinated_arguments_and_identity_fields():
    with pytest.raises(ValidationError):
        CustomerLookupInput.model_validate(
            {
                "tenant_id": "tenant-acme",
                "customer_id": "cust-1",
                "reason": "support troubleshooting",
                "refund_customer": True,
            }
        )
