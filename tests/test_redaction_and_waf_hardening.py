from __future__ import annotations

from pathlib import Path

from maci.audit import AuditEvent, AuditEventType, AuditLogger
from maci.conversation import ConversationStore
from maci.redaction import RedactionService
from maci.schemas import TenantContext


def test_redaction_service_masks_email_token_phone_and_card() -> None:
    redactor = RedactionService(enabled=True, stable_salt="test")
    text = "Email alice@example.com, token Bearer abcdefghijklmnopqrstuvwxyz, card 4111 1111 1111 1111, phone +34 603 22 8660"

    result = redactor.redact_text(text)

    assert result.redacted is True
    assert "alice@example.com" not in result.value
    assert "abcdefghijklmnopqrstuvwxyz" not in result.value
    assert "4111 1111 1111 1111" not in result.value
    assert "+34 603 22 8660" not in result.value
    assert "[REDACTED:EMAIL:" in result.value
    assert "[REDACTED:AUTH_TOKEN:" in result.value
    assert "[REDACTED:PAYMENT_CARD:" in result.value
    assert "[REDACTED:PHONE:" in result.value
    assert {finding.kind for finding in result.findings} >= {"EMAIL", "AUTH_TOKEN", "PAYMENT_CARD", "PHONE"}


def test_conversation_store_redacts_before_persisting_transcript() -> None:
    store = ConversationStore(redactor=RedactionService(enabled=True, stable_salt="test"))
    context = TenantContext(tenant_id="tenant-acme", user_id="u-alice", request_id="req-1")
    record = store.start_or_resume(context, conversation_id="conv-redact", contains_pii=False)

    message = store.append_user_message(
        context,
        record.conversation_id,
        "Please contact alice@example.com and use card 4111111111111111.",
    )

    assert message.redaction_status == "redacted"
    assert message.pii_findings
    assert "alice@example.com" not in str(message.content)
    assert "4111111111111111" not in str(message.content)
    assert store.get("tenant-acme", "conv-redact").contains_pii is True  # type: ignore[union-attr]


def test_audit_logger_redacts_message_and_attributes_before_hashing() -> None:
    logger = AuditLogger(redactor=RedactionService(enabled=True, stable_salt="test"))
    event = AuditEvent(
        request_id="req-1",
        tenant_id="tenant-acme",
        event_type=AuditEventType.REQUEST_RECEIVED,
        message="customer email alice@example.com",
        attributes={"authorization": "Bearer very-secret-token-value", "nested": {"phone": "+34 603 22 8660"}},
    )

    redacted = logger._redact_event(event)  # intentional unit-level invariant check

    dumped = str(redacted.model_dump(mode="json"))
    assert "alice@example.com" not in dumped
    assert "very-secret-token-value" not in dumped
    assert "+34 603 22 8660" not in dumped
    assert redacted.attributes["pii_redaction_status"] == "redacted"
    assert redacted.attributes["pii_findings"]


def test_terraform_contains_api_waf_and_stage_throttling() -> None:
    root = Path(__file__).resolve().parents[1]
    api_main = (root / "infra/terraform/modules/api/main.tf").read_text()
    api_vars = (root / "infra/terraform/modules/api/variables.tf").read_text()
    root_main = (root / "infra/terraform/main.tf").read_text()

    assert "default_route_settings" in api_main
    assert "throttling_burst_limit" in api_main
    assert "aws_wafv2_web_acl" in api_main
    assert "rate_based_statement" in api_main
    assert "AWSManagedRulesCommonRuleSet" in api_main
    assert "AWSManagedRulesKnownBadInputsRuleSet" in api_main
    assert "aws_wafv2_web_acl_association" in api_main
    assert "variable \"enable_waf\"" in api_vars
    assert "enable_waf                = var.enable_api_waf" in root_main


def test_redaction_does_not_mask_numeric_token_metrics() -> None:
    redactor = RedactionService(enabled=True, stable_salt="test")

    result = redactor.redact_value(
        {
            "input_tokens": 123,
            "output_tokens": 45,
            "total_token_count": 168,
            "access_token": "real-access-token-value",
        },
        path="audit.attributes",
    )

    assert result.value["input_tokens"] == 123
    assert result.value["output_tokens"] == 45
    assert result.value["total_token_count"] == 168
    assert result.value["access_token"].startswith("[REDACTED:SECRET:")
    assert not any("input_tokens" in finding.path for finding in result.findings)
    assert not any("output_tokens" in finding.path for finding in result.findings)


def test_model_invoked_audit_preserves_token_metrics_after_redaction() -> None:
    logger = AuditLogger(redactor=RedactionService(enabled=True, stable_salt="test"))
    event = AuditEvent(
        request_id="req-1",
        tenant_id="tenant-acme",
        event_type=AuditEventType.MODEL_INVOKED,
        message="bedrock gateway invoked",
        attributes={
            "input_tokens": 321,
            "output_tokens": 123,
            "estimated_cost_usd": 0.01,
            "access_token": "real-access-token-value",
        },
    )

    redacted = logger._redact_event(event)

    assert redacted.attributes["input_tokens"] == 321
    assert redacted.attributes["output_tokens"] == 123
    assert redacted.attributes["access_token"].startswith("[REDACTED:SECRET:")
