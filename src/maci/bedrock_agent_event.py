from __future__ import annotations

import json
from typing import Any


class BedrockAgentEventError(ValueError):
    """Raised when a Bedrock Agent action event cannot be normalized."""


def extract_model_parameters(event: dict[str, Any]) -> dict[str, Any]:
    """Normalize model-controlled Bedrock Agent parameters.

    Supports three useful shapes:
    * local tests: the event itself is the payload
    * Lambda/API style: {"body": "{...}"}
    * Bedrock Agent style: {"parameters": [{"name": ..., "value": ...}]}

    Identity fields such as tenant_id/user_id are not stripped here; Pydantic
    strict schemas reject them so impersonation attempts become visible failures.
    """

    if "body" in event:
        body = event["body"]
        if isinstance(body, str):
            return json.loads(body)
        if isinstance(body, dict):
            return body
        raise BedrockAgentEventError("unsupported body payload type")

    if "parameters" in event:
        parameters = event.get("parameters") or []
        if not isinstance(parameters, list):
            raise BedrockAgentEventError("parameters must be a list")
        normalized: dict[str, Any] = {}
        for item in parameters:
            if not isinstance(item, dict) or "name" not in item:
                raise BedrockAgentEventError("invalid parameter item")
            normalized[str(item["name"])] = item.get("value")
        return normalized

    request_body = event.get("requestBody")
    if isinstance(request_body, dict):
        content = request_body.get("content", {})
        if isinstance(content, dict):
            for media in ("application/json", "application/x-www-form-urlencoded"):
                properties = content.get(media, {}).get("properties")
                if isinstance(properties, list):
                    return {str(item["name"]): item.get("value") for item in properties if isinstance(item, dict) and "name" in item}

    # Local direct invocation fallback. Exclude infrastructure keys so tests and
    # examples can call the handler with {sessionAttributes, parameters}-free dicts.
    return {k: v for k, v in event.items() if k not in {"sessionAttributes", "promptSessionAttributes"}}
