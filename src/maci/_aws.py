from __future__ import annotations

from typing import Any


def dynamodb_table(table_name: str) -> Any:
    """Return a DynamoDB Table resource for a configured table name.

    Fails closed on purpose: if a table name is configured but the AWS client
    cannot be constructed, the exception propagates instead of silently degrading
    to an in-memory/demo store. Silent fallback in a deployed environment would
    quietly weaken tenant isolation, kill switches, policy enforcement and audit
    without any operational signal. In-memory/demo behaviour is only used when no
    table name is configured at all (explicit local/test mode).
    """

    import boto3  # type: ignore

    return boto3.resource("dynamodb").Table(table_name)


def s3_client() -> Any:
    """Return an S3 client, failing closed if it cannot be constructed."""

    import boto3  # type: ignore

    return boto3.client("s3")
