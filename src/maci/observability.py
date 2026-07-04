from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import uuid4

from pydantic import Field

from .schemas import StrictModel, TenantContext


class TraceSpan(StrictModel):
    trace_id: str
    span_id: str = Field(default_factory=lambda: uuid4().hex[:16])
    parent_span_id: str | None = None
    name: str
    tenant_id: str
    request_id: str
    user_id: str | None = None
    agent_id: str | None = None
    start_time_unix_nano: int
    end_time_unix_nano: int | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    status: str = "OK"
    error_message: str | None = None


class TraceRecorder:
    """Small OTel-compatible JSON trace recorder.

    It intentionally emits OpenTelemetry-shaped span records without forcing a
    vendor SDK dependency. Production users can forward these events to an OTel
    collector, Langfuse, Phoenix or another backend.
    """

    def __init__(self, trace_id: str | None = None, sink: list[TraceSpan] | None = None) -> None:
        self.trace_id = trace_id or uuid4().hex
        self.sink = sink if sink is not None else []

    @contextmanager
    def span(self, name: str, tenant_context: TenantContext, *, parent_span_id: str | None = None, **attributes: Any) -> Iterator[TraceSpan]:
        span = TraceSpan(
            trace_id=self.trace_id,
            parent_span_id=parent_span_id,
            name=name,
            tenant_id=tenant_context.tenant_id,
            request_id=tenant_context.request_id,
            user_id=tenant_context.user_id,
            agent_id=tenant_context.agent_id,
            start_time_unix_nano=time.time_ns(),
            attributes=attributes,
        )
        try:
            yield span
        except Exception as exc:
            span = span.model_copy(update={"status": "ERROR", "error_message": str(exc), "end_time_unix_nano": time.time_ns()})
            self.sink.append(span)
            _emit(span)
            raise
        else:
            span = span.model_copy(update={"end_time_unix_nano": time.time_ns()})
            self.sink.append(span)
            _emit(span)

    def as_trace_payload(self) -> dict[str, Any]:
        return {"trace_id": self.trace_id, "spans": [span.model_dump(mode="json") for span in self.sink]}

    def to_eval_case(self, *, failure_reason: str, input_text: str, expected_safety_property: str) -> dict[str, Any]:
        return {
            "eval_case_id": f"eval-{self.trace_id[:16]}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "failure_reason": failure_reason,
            "input": input_text,
            "expected_safety_property": expected_safety_property,
            "trace": self.as_trace_payload(),
        }


def _emit(span: TraceSpan) -> None:
    if os.getenv("TRACE_STDOUT", "true").lower() == "true":
        print(json.dumps({"_type": "otel_genai_span", **span.model_dump(mode="json")}, sort_keys=True))
