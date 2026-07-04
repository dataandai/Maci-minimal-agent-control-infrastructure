from __future__ import annotations

import json
from typing import Any


def is_bedrock_agent_event(event: dict[str, Any]) -> bool:
    """Return True when the Lambda was invoked by a Bedrock Agent action group."""

    return event.get("messageVersion") == "1.0" and "actionGroup" in event


def bedrock_function_response(
    event: dict[str, Any],
    status_code: int,
    body: dict[str, Any],
    *,
    response_state: str | None = None,
) -> dict[str, Any]:
    """Build the response shape expected by Bedrock Agent function-details action groups.

    Bedrock Agent action-group Lambdas are not API Gateway proxy integrations. When
    invoked by Bedrock, they must return messageVersion/response/sessionAttributes.
    Local tests and direct invocations can still use API Gateway-like responses.
    """

    if not is_bedrock_agent_event(event):
        return {
            "statusCode": status_code,
            "headers": {"content-type": "application/json"},
            "body": json.dumps(body, sort_keys=True),
        }

    function_response: dict[str, Any] = {
        "responseBody": {
            "TEXT": {
                "body": json.dumps(body, sort_keys=True),
            }
        }
    }
    if response_state:
        function_response["responseState"] = response_state

    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup"),
            "function": event.get("function"),
            "functionResponse": function_response,
        },
        "sessionAttributes": event.get("sessionAttributes", {}),
        "promptSessionAttributes": event.get("promptSessionAttributes", {}),
    }
